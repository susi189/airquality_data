# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project status

Early-stage air quality data project ("AQ Project"). The goal is an MCP server that lets AI assistants query a
dbt-modelled warehouse safely — see `Plan.md` for the full plan, phases, and progress checklist.

There is no warehouse, dbt project, or MCP server yet. Only ingestion exists.

## Layout

All Python code lives in one installable package, `aq`, under `src/` (src layout, built with `uv_build`).

- `src/aq/config.py`: shared paths/settings (`RAW_DIR = data/raw`, relative to the working directory)
- `src/aq/ingest/`: pulls from the Umweltbundesamt air data API (`https://luftdaten.umweltbundesamt.de/api/air-data/v3`)
  - `fetch.py`: `fetch()` gets an endpoint with `httpx`; `save_raw()` writes it to `data/raw/<endpoint>/<YYYY-MM-DD>.json`
  - `transform.py`: `transform_data()` turns the API's index-based arrays into a list of dicts, skipping metadata
    keys (`count`, `indices`, `request`). Handles rows at the top level or under a `data` key.
  - `__main__.py`: `main()` loops over the `components` and `stations` endpoints
- `tests/`: mirrors `src/aq/` (e.g. `tests/ingest/test_transform.py`)
- `data/`: raw API dumps and DuckDB files, gitignored

Planned additions (see `Plan.md`): `dbt_project/` at the top level, plus `src/aq/seed/`, `src/aq/mcp_server/` and
`src/aq/evals/` (with eval cases in `evals/cases/`).

## Working preferences

- Always ask for explicit approval before running commands or making file changes — do not proceed under an
  auto-accept or "just do it" assumption, even for routine/reversible actions. Propose the change or command and
  wait for confirmation first.

## Environment

- Managed with `uv` (not pip/venv directly). Python 3.13 (`.python-version` and `requires-python = ">=3.13"`).
- Dependencies: `httpx`. Dev dependencies: `ruff`, `pytest`.

## Commands

- Run ingestion: `uv run aq-ingest` (or `uv run python -m aq.ingest`)
- Add a dependency: `uv add <package>`
- Sync the environment: `uv sync`
- Add a dev dependency: `uv add --dev <package>`
- Lint: `uv run ruff check .` (auto-fix: `uv run ruff check --fix .`)
- Format: `uv run ruff format .` (check only: `uv run ruff format --check .`)
- Test: `uv run pytest` (single test: `uv run pytest path/to/test_file.py::test_name`)

Ruff config lives in `pyproject.toml`: line length 120, lint rules `E`, `F`, `I`, `B`, `UP`.
