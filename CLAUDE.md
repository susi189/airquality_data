# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project status

Early-stage air quality data project ("AQ Project"). The goal is an MCP server that lets AI assistants query a
dbt-modelled warehouse safely — see `Plan.md` for the full plan, phases, and progress checklist.

Ingestion and the raw DuckDB load exist. There is no dbt project or MCP server yet.

## Layout

All Python code lives in one installable package, `aq`, under `src/` (src layout, built with `uv_build`).

- `src/aq/config.py`: shared paths/settings (`RAW_DIR = data/raw`, `DUCKDB_PATH = data/aq.duckdb`, both relative to
  the working directory)
- `src/aq/ingest/`: pulls from the Umweltbundesamt air data API v4 (`https://luftdaten.umweltbundesamt.de/api/air-data/v4`)
  - `fetch.py`: `fetch()` gets an endpoint with a shared `httpx.Client`; `save_raw()` writes metadata endpoints to
    `data/raw/<endpoint>/<YYYY-MM-DD>.json`. `fetch_measures()` gets one day of hourly values (scope 2) for one
    component across all stations, saved to `data/raw/measures/<component id>/<YYYY-MM-DD>.json`.
  - `transform.py`: `transform_data()` turns flat index-based responses into dicts, skipping metadata keys
    (`count`, `indices`, `request`, `meta`). `transform_measures()` flattens the nested measures response
    (`data -> station id -> date start -> [component id, scope id, value, date end, index]`) into one dict per row.
  - `__main__.py`: pulls `components` and `stations`, then measures for PM10, PM2.5, NO2, O3, SO2 over a date range.
    Days already saved are skipped.
- `src/aq/load/`: loads `data/raw/` into the DuckDB `raw` schema (`raw.components`, `raw.stations`, `raw.measures`)
  - `loader.py`: `load_all()` does a full rebuild in one transaction. Metadata tables use the newest file only;
    measures use all files. Column names are snake_cased (`station id` → `station_id`), values stay as the API
    delivers them (metadata all `VARCHAR`; measures typed via `MEASURES_COLUMNS`). Every row gets `_source_file`
    and `_loaded_at`. Records are streamed to a temporary NDJSON file and bulk-loaded with `read_json`.
  - Note: the measures column `index` is a SQL keyword in some contexts; quote it as `"index"` in queries.
- `tests/`: mirrors `src/aq/` (`tests/ingest/`, `tests/load/`); DuckDB tests use in-memory databases
  - `tests/ingest/fixtures/`: trimmed real API responses used as test input
  - HTTP calls in tests use `httpx.MockTransport`; tests never call the live API
- `data/`: raw API dumps and DuckDB files, gitignored

Planned additions (see `Plan.md` for the step-by-step checklist):
- `src/aq/seed/` (`aq-seed`: synthetic business data with Faker) — next step (Plan 1.3)
- `dbt_project/` at the top level
- Dagster orchestration (Plan Phase 1b), once `aq-load` and dbt exist
- `src/aq/mcp_server/` and `src/aq/evals/` (with eval cases in `evals/cases/`)

## API facts (verified Oct 2026)

- Measure hours run 1-24 and mark the end of the hour (`time_from=1` = 00:00-01:00). Times are local CET/CEST.
- Missing measurements come back as `null` value (and `null` index), not as absent rows.
- The `index` field's meaning is not yet known; keep it raw, don't interpret it.
- Component ids: PM10=1, PM2.5=9 (code `PM2`), NO2=5, O3=3, SO2=4. CO (2) has no active hourly stations.
- `/measures/limits` is data availability per scope/component/station (first/last date), not request limits.
- `stations` returns every station ever operated (~2,400, including closed ones); all values are strings and missing
  values are empty strings (`''`), not `null`.

## Working preferences

- Always ask for explicit approval before running commands or making file changes — do not proceed under an
  auto-accept or "just do it" assumption, even for routine/reversible actions. Propose the change or command and
  wait for confirmation first.

## Environment

- Managed with `uv` (not pip/venv directly). Python 3.13 (`.python-version` and `requires-python = ">=3.13"`).
- Dependencies: `httpx`, `duckdb`. Dev dependencies: `ruff`, `pytest`.

## Commands

- Run ingestion: `uv run aq-ingest --start YYYY-MM-DD --end YYYY-MM-DD` (defaults to yesterday; calls the live API)
- Load raw files into DuckDB: `uv run aq-load` (rebuilds the `raw` tables in `data/aq.duckdb`)
- Add a dependency: `uv add <package>`
- Sync the environment: `uv sync`
- Add a dev dependency: `uv add --dev <package>`
- Lint: `uv run ruff check .` (auto-fix: `uv run ruff check --fix .`)
- Format: `uv run ruff format .` (check only: `uv run ruff format --check .`)
- Test: `uv run pytest` (single test: `uv run pytest path/to/test_file.py::test_name`)

Ruff config lives in `pyproject.toml`: line length 120, lint rules `E`, `F`, `I`, `B`, `UP`.
