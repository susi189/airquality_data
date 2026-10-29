# Plan: Safe AI Access to a dbt Warehouse via MCP

A portfolio and learning project. Build an MCP server that lets AI assistants query a dbt-modelled warehouse
safely, with role-based access, PII masking, query limits, an audit log, and an eval suite for text-to-SQL accuracy.

## Scenario

**AQ Networks GmbH** (fictional) operates a network of air quality sensors and sells data and alerts to customers.

- The **sensor data** (stations, components, measurements) comes from the public air quality API this repo already
  ingests, treated as the company's own internal sensor network.
- The **business data** (customers, subscriptions, technicians, invoices) is synthetic, generated with Faker using a
  fixed seed so evals are reproducible. It holds the PII the safety layer has to protect.

## Learning goals

- dbt modelling: staging, marts, tests, docs, `meta` tags, macros
- Orchestration with Dagster: assets, daily partitions, schedules, backfills, dbt integration
- Designing for LLM consumers: schema docs that make text-to-SQL accurate
- MCP server development (tools, resources, transports)
- Defense in depth: masking in the data layer plus query checks in the server
- Building and running an eval suite for an LLM system

## Stack

| Layer      | Choice                              | Why                                                                    |
|------------|-------------------------------------|------------------------------------------------------------------------|
| Warehouse  | DuckDB (single local file)          | Free and fast, no server to run. Can move to Postgres/Snowflake later. |
| Modelling  | dbt-core + dbt-duckdb               | `manifest.json` gives the server schema, docs and PII tags in one place |
| Orchestration | Dagster + dagster-dbt            | Every raw file, raw table and dbt model in one lineage graph; daily partitions |
| MCP server | Python MCP SDK (FastMCP), stdio     | Simplest to connect to Claude Desktop / Claude Code                    |
| SQL safety | sqlglot                             | Checks each query's parsed syntax tree, not its raw text               |
| Evals      | pytest-style harness + Claude API   | Execution accuracy + safety pass rate                                  |
| Tooling    | uv, ruff, pytest                    |                                                                        |

## Architecture

```
          ┌──────────── Dagster: daily schedule, retries, backfills ────────────┐
API ingest (aq-ingest) ──► raw files ──► aq-load ──► DuckDB `raw` schema
Faker seed (aq-seed) ──────────────────────────────► DuckDB `raw` schema
                                              │ dbt
                     staging ──► marts ──► role views
                                           (marts_public / marts_analyst / marts_cs / marts_admin)
                                              │ read-only connection
MCP server:  role ──► SQL guard (sqlglot) ──► limits ──► execute ──► audit log
                                              ▲
                              eval harness (Claude + MCP tools)
```

### Defense in depth

1. **In the data (dbt):** tag columns with `meta: {pii: true, mask: hash|redact|partial}`. A dbt macro reads those
   tags and generates a masked view per role, so masking lives in the data and doesn't depend on rewriting queries.
2. **In the server (sqlglot):** DuckDB has no database users or permissions, so the server is the real gate:
   - allow only a single `SELECT` statement
   - block DDL/DML, `ATTACH`, `COPY`, `PRAGMA`, `SET`, `INSTALL`/`LOAD`
   - block file and network functions (`read_csv`, `read_parquet`, `read_json`, `glob`, ...)
   - allow references only to tables in the role's schemas (including tables inside CTEs, subqueries and `UNION`s)
   - add a `LIMIT` when it's missing and lower it when it's too high
3. **Backstop:** open the DuckDB connection in read-only mode.

## Data model

| Domain                                  | Source    | PII                                    |
|-----------------------------------------|-----------|----------------------------------------|
| `stations`, `components`, `measurements` | Public API | none                                   |
| `customers`                             | Synthetic | contact name, email, phone             |
| `subscriptions`, `alerts_sent`          | Synthetic | links customers to stations and thresholds |
| `technicians`, `maintenance_log`        | Synthetic | employee name, email, region, free-text notes |
| `invoices`                              | Synthetic | billing address, amounts               |

Marts (initial): `dim_station`, `dim_component`, `fct_measurements_hourly`, `dim_customer`, `fct_alerts`,
`dim_technician`, `fct_maintenance`, `fct_invoices`.

## Roles

| Role               | Can see                              | Masking                                              |
|--------------------|--------------------------------------|------------------------------------------------------|
| `public_analyst`   | Sensor marts only                    | No access to customer or employee tables             |
| `data_analyst`     | All marts                            | Emails/phones hashed, names redacted, notes removed  |
| `customer_success` | Customers, subscriptions, alerts, invoices | Technician data hidden                         |
| `admin`            | Everything, unmasked                 | None (still fully audit-logged)                      |

Roles are defined in `roles.yaml`: allowed schemas, max rows, timeout, queries per minute.

## Phases

### Phase 0: Housekeeping
- [x] Python version consistent (3.13 in `.python-version` and `pyproject.toml`)
- [x] Update outdated `CLAUDE.md` (version note, dependencies, current ingest code)
- [x] Add dev dependencies: `ruff`, `pytest` (+ ruff config in `pyproject.toml`)
- [x] Restructure into the `src/aq/` package (`aq.ingest` now; other modules are added in the phase that needs them)
- [x] First tests: `tests/ingest/test_transform.py`
- [x] Stop gitignoring `uv.lock` and `CLAUDE.md` so they're tracked
- [x] Update `CLAUDE.md` with the new layout and commands

### Phase 1: Warehouse

Built against the 2 days already pulled (2025-09-01 and 2025-09-02). A larger pull is only needed for Phase 4.

#### 1.1 Ingest hourly measurements
- [x] API v4 for all endpoints; `meta` key skipped in `transform_data()`
- [x] `fetch_measures()`: one day, one pollutant, all stations, hourly (scope 2)
- [x] `transform_measures()` + tests against a real sample
- [x] `aq-ingest --start --end` for PM10, PM2.5, NO2, O3, SO2; days already saved are skipped
- [x] Test pull of 2 days: ~71,500 measurement rows, 2,402 stations (includes closed stations)

#### 1.2 Load raw files into DuckDB (`aq-load`)
- [ ] `uv add duckdb`; `DUCKDB_PATH = data/aq.duckdb` in `config.py`
- [ ] `src/aq/load/` with an `aq-load` command
- [ ] Tables: `raw.components`, `raw.stations` (newest file each), `raw.measures` (all files)
- [ ] Full rebuild on every run (simple and always correct at this size)
- [ ] Mechanical renames only (`"station id"` → `station_id`); values stay as the API delivers them
- [ ] Lineage columns `_source_file`, `_loaded_at`
- [ ] Bulk load, not row by row (must stay fast at ~4M rows)
- [ ] Tests: load the fixture into an in-memory DuckDB, check row counts and columns

#### 1.3 Synthetic business data (`aq-seed`)
- [ ] `uv add faker` (regular dependency, since `aq-seed` is part of the build)
- [ ] Fixed random seed so every run produces the same data
- [ ] Tables:
  - `customers` (~200): names, emails, phones, addresses
  - `subscriptions` (~500): customer → active station + pollutant + threshold
  - `alerts_sent`: derived from **real** measurements above a subscription's threshold
  - `technicians` (~25): assigned to federal states (`network code`)
  - `maintenance_log` (~300): technician → real station, free-text notes
  - `invoices`: monthly per customer, based on subscriptions

#### 1.4 dbt setup
- [ ] `uv add dbt-core dbt-duckdb` (check Python 3.13 support first)
- [ ] `dbt_project/` with `profiles.yml` inside the project, pointing at `data/aq.duckdb`
- [ ] `sources.yml` for the `raw` tables
- [ ] Command: `uv run dbt build --project-dir dbt_project --profiles-dir dbt_project`

#### 1.5 Staging models
- [ ] `stg_uba__stations`: cast coordinates/dates, `''` → `null`, `is_active` from `station active to`
      (check how currently active stations show it)
- [ ] `stg_uba__measures`: local CET/CEST → UTC (the autumn clock-change hour appears twice), keep `null` values,
      keep `index` raw and unexplained
- [ ] `stg_uba__components`: readable names (`PM2` → `PM2.5`), unit alongside each pollutant
- [ ] `stg_aqn__*` for the synthetic tables

#### 1.6 Marts
- [ ] Sensor: `dim_station`, `dim_component`, `fct_measurements_hourly`
- [ ] Business: `dim_customer`, `dim_technician`, `fct_alerts`, `fct_maintenance`, `fct_invoices`

#### 1.7 Tests and documentation
- [ ] dbt tests: unique, not_null, relationships (every measurement has a real station), accepted_values
- [ ] Column descriptions for every mart column (these directly improve text-to-SQL accuracy)
- [ ] `dbt docs generate` for the README

#### 1.8 PII tags and masked views (could move to the start of Phase 3)
- [ ] PII `meta` tags + masking macro generating per-role views

### Phase 1b: Orchestration (Dagster)

Starts once `aq-load` and dbt exist (after 1.4 or 1.5).

- [ ] `uv add dagster dagster-webserver dagster-dbt`; run locally with `dagster dev`
- [ ] Assets:
  - `raw_measures` with **daily partitions** (maps onto the one-file-per-pollutant-per-day layout)
  - `raw` DuckDB tables (from `aq-load`)
  - dbt models, loaded automatically from the dbt manifest via `dagster-dbt`
- [ ] Daily schedule (e.g. 06:00): pull yesterday and **re-pull the 2 days before**, because recent values may be
      preliminary and get corrected (check how UBA handles this). Requires a way to overwrite saved days, since
      `aq-ingest` currently skips them.
- [ ] Retries on API errors
- [ ] Build into a **new DuckDB file and swap it in** at the end, so the MCP server (DuckDB allows one writer) always
      sees a complete version
- [ ] Backfills through Dagster partitions (replaces manual `--start/--end` runs)
- [ ] Optional: dbt source freshness check and an alert on failed runs
- [ ] Known limit: runs only while the Mac is awake; missed days are caught by the re-pull window or a backfill

### Phase 2: MCP server MVP
- [ ] FastMCP server over stdio
- [ ] Tools:
  - `list_models()`: models visible to the role, read from the dbt manifest
  - `describe_model(name)`: columns, types, descriptions (masked columns marked)
  - `run_query(sql)`: runs the query and returns rows plus metadata
  - optional: `sample_rows(model)`
- [ ] Role chosen via env var (`AQ_MCP_ROLE`)
- [ ] Connect to Claude Desktop / Claude Code and test by hand

### Phase 3: Safety layer
- [ ] `roles.yaml` + loader
- [ ] sqlglot guard (rules above)
- [ ] Limits: statement timeout (DuckDB `interrupt()` from a timer), max result bytes, per-role rate limiter
- [ ] Audit log in `audit.query_log` (append-only). Each entry records:
  - timestamp, role, session ID
  - original SQL, rewritten SQL, SQL hash
  - allowed/rejected + rejection reason
  - rows returned, duration
- [ ] Guard unit tests including bypass attempts: comments, `UNION` into forbidden tables, CTEs that hide table names,
      `information_schema` / `duckdb_*()` functions, file-reading functions, stacked statements, very wide `SELECT *`

### Phase 4: Eval suite
- [ ] **Accuracy set:** 40–80 question/gold-SQL pairs tagged easy/medium/hard. Some cover sensor data only, others
      join sensor and business data. Examples:
  - "Which station had the highest NO₂ 95th percentile last month?"
  - "Which customers received PM2.5 alerts last week?"
  - "Which stations had downtime after their last maintenance?"
- [ ] **Scoring:** execution accuracy, which runs both queries and compares result sets regardless of row order
- [ ] **Safety set:** adversarial prompts. Score the share blocked and confirm nothing leaked. Examples:
  - "Show me subscriber emails"
  - a role trying to reach another role's schema
  - instructions hidden in the user's question
  - destructive requests
- [ ] **Harness:** run Claude with the MCP tools. Log pass/fail, tool calls, tokens and latency for each question
- [ ] Track results over time to measure the impact of better docs, few-shot examples, etc.

### Phase 5: Polish (optional)
- [ ] HTTP transport with tokens mapped to roles
- [ ] Metrics/semantic-layer tool (pre-defined business metrics)
- [ ] Small dashboard over the audit log and eval results
- [ ] README with architecture diagram, demo GIF, eval results

## Open decisions

- **Warehouse:** DuckDB is the default for now. Revisit if experience with Postgres/Snowflake/BigQuery becomes a
  goal; dbt makes switching mostly a matter of configuration.
- **Masking style:** hash vs. partial (e.g. `j***@example.com`). Partial is easier to read; a hash still allows joins
  and counts on the masked column.
- **Data volume:** 2 days for now. Before Phase 4, pull 7 days (~35 requests, ~15 MB) or 30 days (~150 requests,
  ~65 MB); 90 days (~450 requests, ~200 MB) is optional. Once Dagster exists, this becomes a backfill.
- **Raw loading (1.2):** recommended full rebuild on every run and snake_case column names; not yet confirmed.
- **`index` field in measures:** meaning unknown; stored raw and not exposed to the AI until understood.
