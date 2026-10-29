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
- Designing for LLM consumers: schema docs that make text-to-SQL accurate
- MCP server development (tools, resources, transports)
- Defense in depth: masking in the data layer plus query checks in the server
- Building and running an eval suite for an LLM system

## Stack

| Layer      | Choice                              | Why                                                                    |
|------------|-------------------------------------|------------------------------------------------------------------------|
| Warehouse  | DuckDB (single local file)          | Free and fast, no server to run. Can move to Postgres/Snowflake later. |
| Modelling  | dbt-core + dbt-duckdb               | `manifest.json` gives the server schema, docs and PII tags in one place |
| MCP server | Python MCP SDK (FastMCP), stdio     | Simplest to connect to Claude Desktop / Claude Code                    |
| SQL safety | sqlglot                             | Checks each query's parsed syntax tree, not its raw text               |
| Evals      | pytest-style harness + Claude API   | Execution accuracy + safety pass rate                                  |
| Tooling    | uv, ruff, pytest                    |                                                                        |

## Architecture

```
API ingest (existing) ──► raw files ──► DuckDB `raw` schema
Faker seed script ─────────────────────► DuckDB `raw` schema
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
- [ ] Load existing API outputs into DuckDB `raw` schema
- [ ] Faker seed script for the business tables (fixed seed)
- [ ] dbt project with dbt-duckdb: staging models, marts
- [ ] dbt tests (unique, not_null, relationships, accepted_values)
- [ ] Column descriptions for every mart column (these directly improve text-to-SQL accuracy)
- [ ] PII `meta` tags + masking macro generating per-role views

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
