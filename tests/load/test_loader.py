import json
import shutil
from pathlib import Path

import duckdb
import pytest

from aq.load.loader import MEASURES_COLUMNS, latest_file, load_all, to_snake

MEASURES_FIXTURE = Path(__file__).parents[1] / "ingest" / "fixtures" / "measures_pm10_sample.json"


def write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")


@pytest.fixture
def raw_dir(tmp_path: Path) -> Path:
    raw = tmp_path / "raw"
    meta = {"source": "Umweltbundesamt"}
    write_json(
        raw / "components" / "2026-10-01.json",
        {"count": 1, "indices": ["component id", "component code"], "1": ["1", "OLD"], "meta": meta},
    )
    write_json(
        raw / "components" / "2026-10-29.json",
        {
            "count": 2,
            "indices": ["component id", "component code"],
            "1": ["1", "PM10"],
            "9": ["9", "PM2"],
            "meta": meta,
        },
    )
    write_json(
        raw / "stations" / "2026-10-29.json",
        {
            "request": {"lang": "en"},
            "indices": ["station id", "station name", "station synonym"],
            "data": {"219": ["219", "Weinheim", ""]},
            "count": 1,
            "meta": meta,
        },
    )
    (raw / "measures" / "1").mkdir(parents=True)
    shutil.copy(MEASURES_FIXTURE, raw / "measures" / "1" / "2025-09-01.json")
    return raw


def test_to_snake():
    assert to_snake("station active from") == "station_active_from"
    assert to_snake("Component ID") == "component_id"


def test_latest_file(raw_dir: Path):
    assert latest_file(raw_dir / "components").name == "2026-10-29.json"
    assert latest_file(raw_dir / "missing") is None


def test_load_all_counts(raw_dir: Path):
    with duckdb.connect() as con:
        assert load_all(con, raw_dir) == {"components": 2, "stations": 1, "measures": 3}


def test_rerun_replaces_instead_of_appending(raw_dir: Path):
    with duckdb.connect() as con:
        load_all(con, raw_dir)
        assert load_all(con, raw_dir) == {"components": 2, "stations": 1, "measures": 3}


def test_measures_columns_and_types(raw_dir: Path):
    with duckdb.connect() as con:
        load_all(con, raw_dir)
        columns = con.execute("describe raw.measures").fetchall()

    assert [(name, type_) for name, type_, *_ in columns] == [
        *MEASURES_COLUMNS.items(),
        ("_source_file", "VARCHAR"),
        ("_loaded_at", "TIMESTAMP WITH TIME ZONE"),
    ]


def test_measures_values_stay_raw(raw_dir: Path):
    with duckdb.connect() as con:
        load_all(con, raw_dir)
        rows = con.execute(
            'select station_id, date_start, value, "index", _source_file from raw.measures order by 1, 2'
        ).fetchall()

    source = (raw_dir / "measures/1/2025-09-01.json").as_posix()
    assert rows == [
        ("107", "2025-09-01 00:00:00", None, None, source),
        ("21", "2025-09-01 00:00:00", 9.0, "1", source),
        ("21", "2025-09-01 01:00:00", 8.0, "1", source),
    ]


def test_reference_tables_use_newest_file_and_keep_strings(raw_dir: Path):
    with duckdb.connect() as con:
        load_all(con, raw_dir)
        components = con.execute("select component_id, component_code from raw.components order by 1").fetchall()
        stations = con.execute("select station_id, station_name, station_synonym from raw.stations").fetchall()

    assert components == [("1", "PM10"), ("9", "PM2")]
    assert stations == [("219", "Weinheim", "")]
