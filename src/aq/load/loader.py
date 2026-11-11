import json
import tempfile
from collections.abc import Callable
from pathlib import Path

import duckdb

from aq.ingest.transform import transform_data, transform_measures

REFERENCE_TABLES = ["components", "stations"]
# Explicit types keep values as the API delivers them; DuckDB would otherwise guess dates from strings.
MEASURES_COLUMNS = {
    "station_id": "VARCHAR",
    "date_start": "VARCHAR",
    "component_id": "INTEGER",
    "scope_id": "INTEGER",
    "value": "DOUBLE",
    "date_end": "VARCHAR",
    "index": "VARCHAR",
}


def to_snake(name: str) -> str:
    return "_".join(name.lower().split())


def latest_file(folder: Path) -> Path | None:
    # Files are named YYYY-MM-DD.json, so name order is date order
    files = sorted(folder.glob("*.json"))
    return files[-1] if files else None


def read_records(path: Path, transform: Callable[[dict], list[dict]]) -> list[dict]:
    response = json.loads(path.read_text(encoding="utf-8"))
    records = []
    for record in transform(response):
        row = {to_snake(key): value for key, value in record.items()}
        row["_source_file"] = path.as_posix()
        records.append(row)
    return records


def load_table(
    con: duckdb.DuckDBPyConnection,
    table: str,
    files: list[Path],
    transform: Callable[[dict], list[dict]],
    columns: dict[str, str] | None = None,
) -> int:
    # Records are streamed file by file into one newline-delimited JSON file, then bulk-loaded by DuckDB.
    # Without explicit columns (reference tables) every column is VARCHAR, matching the API's all-string values.
    with tempfile.TemporaryDirectory() as tmp:
        ndjson = Path(tmp) / f"{table}.ndjson"
        with ndjson.open("w", encoding="utf-8") as f:
            for path in files:
                for record in read_records(path, transform):
                    if columns is None:
                        columns = {key: "VARCHAR" for key in record if key != "_source_file"}
                    f.write(json.dumps(record, ensure_ascii=False) + "\n")

        if columns is None:
            raise ValueError(f"No records found for {table} in {[str(p) for p in files]}")

        all_columns = {**columns, "_source_file": "VARCHAR"}
        columns_sql = ", ".join(f"'{name}': '{type_}'" for name, type_ in all_columns.items())
        con.execute(
            f"""
            create or replace table raw.{table} as
            select *, current_timestamp as _loaded_at
            from read_json('{ndjson.as_posix()}', format = 'newline_delimited', columns = {{{columns_sql}}})
            """
        )
    return con.execute(f"select count(*) from raw.{table}").fetchone()[0]


def load_all(con: duckdb.DuckDBPyConnection, raw_dir: Path) -> dict[str, int]:
    # Full rebuild in one transaction: either every table is replaced or none is.
    counts = {}
    con.execute("create schema if not exists raw")
    con.begin()
    try:
        for table in REFERENCE_TABLES:
            path = latest_file(raw_dir / table)
            if path is not None:
                counts[table] = load_table(con, table, [path], transform_data)

        measure_files = sorted((raw_dir / "measures").glob("*/*.json"))
        if measure_files:
            counts["measures"] = load_table(con, "measures", measure_files, transform_measures, MEASURES_COLUMNS)
        con.commit()
    except Exception:
        con.rollback()
        raise
    return counts
