import json
from pathlib import Path

from aq.ingest.transform import transform_data, transform_measures

FIXTURES = Path(__file__).parent / "fixtures"


def test_rows_at_top_level():
    response = {
        "count": 2,
        "indices": ["id", "code", "symbol"],
        "1": ["1", "PM10", "PM₁₀"],
        "2": ["5", "NO2", "NO₂"],
    }

    assert transform_data(response) == [
        {"id": "1", "code": "PM10", "symbol": "PM₁₀"},
        {"id": "5", "code": "NO2", "symbol": "NO₂"},
    ]


def test_rows_under_data_key():
    response = {
        "request": {"lang": "en"},
        "indices": ["id", "code"],
        "data": {"10": ["10", "DEBB021"]},
        "count": 1,
    }

    assert transform_data(response) == [{"id": "10", "code": "DEBB021"}]


def test_no_rows():
    assert transform_data({"count": 0, "indices": ["id"]}) == []


def test_meta_key_is_skipped():
    # v4 responses carry a top-level `meta` dict next to the rows
    response = {
        "count": 1,
        "indices": ["id", "code"],
        "1": ["1", "PM10"],
        "meta": {"source": "Umweltbundesamt", "lang": "en"},
    }

    assert transform_data(response) == [{"id": "1", "code": "PM10"}]


def test_measures_from_real_sample():
    # Trimmed from a real /measures/json response: PM10, hourly, 2025-09-01
    response = json.loads((FIXTURES / "measures_pm10_sample.json").read_text(encoding="utf-8"))

    assert transform_measures(response) == [
        {
            "station id": "21",
            "date start": "2025-09-01 00:00:00",
            "component id": 1,
            "scope id": 2,
            "value": 9,
            "date end": "2025-09-01 01:00:00",
            "index": "1",
        },
        {
            "station id": "21",
            "date start": "2025-09-01 01:00:00",
            "component id": 1,
            "scope id": 2,
            "value": 8,
            "date end": "2025-09-01 02:00:00",
            "index": "1",
        },
        {
            "station id": "107",
            "date start": "2025-09-01 00:00:00",
            "component id": 1,
            "scope id": 2,
            "value": None,
            "date end": "2025-09-01 01:00:00",
            "index": None,
        },
    ]


def test_measures_empty_data():
    response = {
        "indices": {"data": {"station id": {"date start": ["component id", "scope id", "value", "date end", "index"]}}},
        "data": {},
    }

    assert transform_measures(response) == []
