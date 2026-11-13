# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project status

Early-stage air quality data project ("AQ Project"). The goal is an MCP server that lets AI assistants query a
dbt-modelled warehouse safely — see `Plan.md` for the full plan, phases, and progress checklist.

Ingestion, the raw DuckDB load, and a dbt project with a first staging model exist. There is no MCP server yet.

## Layout

All Python code lives in one installable package, `aq`, under `src/` (src layout, built with `uv_build`).

- `src/aq/config.py`: shared paths/settings (`RAW_DIR = data/raw`, `DUCKDB_PATH = data/aq.duckdb`, both relative to
  the working directory)
- `src/aq/ingest/`: pulls from the Umweltbundesamt air data API v4 (`https://luftdaten.umweltbundesamt.de/api/air-data/v4`)
  - `fetch.py`: `fetch()` gets an endpoint with a shared `httpx.Client`; `save_raw()` writes reference endpoints to
    `data/raw/<endpoint>/<YYYY-MM-DD>.json`. `fetch_measures()` gets one day of hourly values (scope 2) for one
    component across all stations, saved to `data/raw/measures/<component id>/<YYYY-MM-DD>.json`.
  - `transform.py`: `transform_data()` turns flat index-based responses into dicts, skipping metadata keys
    (`count`, `indices`, `request`, `meta`). `transform_measures()` flattens the nested measures response
    (`data -> station id -> date start -> [component id, scope id, value, date end, index]`) into one dict per row.
  - `__main__.py`: pulls `components` and `stations`, then measures for PM10, PM2.5, NO2, O3, SO2 over a date range.
    Days already saved are skipped.
- `src/aq/load/`: loads `data/raw/` into the DuckDB `raw` schema (`raw.components`, `raw.stations`, `raw.measures`)
  - `loader.py`: `load_all()` does a full rebuild in one transaction. Reference tables use the newest file only;
    measures use all files. Column names are snake_cased (`station id` → `station_id`), values stay as the API
    delivers them (reference tables all `VARCHAR`; measures typed via `MEASURES_COLUMNS`). Every row gets `_source_file`
    and `_loaded_at`. Records are streamed to a temporary NDJSON file and bulk-loaded with `read_json`.
  - Note: the measures column `index` is a SQL keyword in some contexts; quote it as `"index"` in queries.
- `tests/`: mirrors `src/aq/` (`tests/ingest/`, `tests/load/`); DuckDB tests use in-memory databases
  - `tests/ingest/fixtures/`: trimmed real API responses used as test input
  - HTTP calls in tests use `httpx.MockTransport`; tests never call the live API
- `data/`: raw API dumps and DuckDB files, gitignored
- `dbt_project/`: dbt project `aq_warehouse` (dbt-core + dbt-duckdb), building on the `raw` tables
  - `profiles.yml` lives in the project (not `~/.dbt/`). Its DuckDB `path` (`../data/aq.duckdb`) is resolved
    relative to `dbt_project/`, not the directory dbt is run from.
  - `dbt_project.yml`: `models/staging/` → views in schema `staging`; `models/marts/` → tables in schema `marts`
  - `macros/generate_schema_name.sql`: uses custom schema names as-is (`staging`, not dbt's default `main_staging`).
    Don't comment it out with `--`: Jinja still runs inside SQL comments and the `--` ends up in the schema name.
  - `models/staging/uba/`: `_uba_sources.yml` declares source `uba` (schema `raw`); one `stg_uba__<table>.sql` per
    raw table. Exists so far: `stg_uba__components` (integer id, `PM2` → `PM2.5` as `pollutant`, `unit`).
  - Naming: `stg_<source>__<table>` for staging; sources `uba` (API data) and later `aqn` (synthetic business data)

Planned additions (see `Plan.md` for the step-by-step checklist):
- `stg_uba__stations` and `stg_uba__measures` — next step (Plan 1.5)
- `src/aq/seed/` (`aq-seed`: synthetic business data with Faker) (Plan 1.3, after 1.5)
- Dagster orchestration (Plan Phase 1b)
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
- Dependencies: `httpx`, `duckdb`, `dbt-core`, `dbt-duckdb`. Dev dependencies: `ruff`, `pytest`.
- DuckDB allows either **one** read-write process or any number of read-only processes on `data/aq.duckdb`. Any
  open session (DuckDB CLI or UI, even with `-readonly`) blocks `aq-load` and `dbt build` with a lock error.
  Close it (`.exit`) before building.

## Commands

- Run ingestion: `uv run aq-ingest --start YYYY-MM-DD --end YYYY-MM-DD` (defaults to yesterday; calls the live API)
- Load raw files into DuckDB: `uv run aq-load` (rebuilds the `raw` tables in `data/aq.duckdb`)
- dbt, from inside `dbt_project/`: `uv run dbt debug` / `uv run dbt build` / `uv run dbt run --select <model>`
  (from the repo root, add `--project-dir dbt_project --profiles-dir dbt_project`). Prefer `dbt build`: it runs
  tests and skips downstream models when one fails.
- Pipeline order: `aq-ingest` → `aq-load` → `dbt build`. Python commands run from the repo root (paths in
  `config.py` are relative to the working directory).
- Explore: `duckdb -readonly data/aq.duckdb` (DuckDB CLI, `brew install duckdb`); `.exit` before the next build
- Add a dependency: `uv add <package>`
- Sync the environment: `uv sync`
- Add a dev dependency: `uv add --dev <package>`
- Lint: `uv run ruff check .` (auto-fix: `uv run ruff check --fix .`)
- Format: `uv run ruff format .` (check only: `uv run ruff format --check .`)
- Test: `uv run pytest` (single test: `uv run pytest path/to/test_file.py::test_name`)

Ruff config lives in `pyproject.toml`: line length 120, lint rules `E`, `F`, `I`, `B`, `UP`.
