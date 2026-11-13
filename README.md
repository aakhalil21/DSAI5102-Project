# NYC Taxi Demand and Fare Analytics Pipeline

DSAI5102 end-to-end batch data pipeline using NYC Yellow Taxi
Trip Records and the official Taxi Zone Lookup Table.

## Problem and motivation

NYC Yellow Taxi trip data contains millions of detailed records, but the
raw monthly files are not immediately suitable for dependable analysis.
They include invalid timestamps and locations, unusual trip values,
financial adjustments, missing values and records outside the intended
period. Manually combining and cleaning the files would be difficult to
repeat and easy to perform inconsistently.

This project builds a reproducible batch pipeline that validates the
official source files, preserves traceability, separates accepted and
rejected records, creates an analytical warehouse and serves an
interactive dashboard. It supports questions such as:

- How do trip activity and recorded passenger charges change over time?
- Which weekdays and pickup hours have the most recorded trips?
- Which boroughs and taxi zones generate the most pickups?
- How are eligible trips and charges distributed by payment method?

Trips in this project measure recorded taxi activity, not unmet demand.

## Current scope

The pipeline processes January through June 2025.

The verified six-month build processes 24,083,384 source rows:

- 23,886,241 accepted trips
- 197,143 rejected trips
- 181 daily summary rows
- 12 successful dbt model builds and 43 passing dbt data tests
- 11 passing focused Python tests

## Tools

- Python: downloading and profiling data
- Prefect: pipeline orchestration
- dbt: SQL transformations and data-quality tests
- DuckDB: analytical warehouse
- Streamlit and Plotly: interactive dashboard
- Docker Compose: running the project
- GitHub: team collaboration and version control

## Architecture

```mermaid
flowchart LR
    A[NYC TLC monthly Parquet files] --> B[Python ingestion]
    Z[NYC TLC taxi-zone CSV] --> B
    B --> C[data/raw immutable source files]
    B --> D[Source manifest and SHA-256 checksums]
    C --> E[Python data profiling]
    C --> F[dbt staging and quality models]
    F --> G[Accepted fact_trips]
    F --> H[rejected_trips with reasons]
    G --> I[Dimensions and analytical marts]
    H --> J[Candidate DuckDB validation]
    I --> J
    J -->|All checks pass| K[Published DuckDB warehouse]
    K --> L[Streamlit and Plotly dashboard]
    M[Prefect] -. orchestrates .-> B
    M -. orchestrates .-> E
    M -. orchestrates .-> F
    M -. orchestrates .-> J
    N[Docker Compose] -. reproducible runtime .-> M
    N -. reproducible runtime .-> L
```

The project uses a batch design because the TLC publishes historical
monthly files and the analytical use case does not require real-time
updates.

## Component roles

| Component | Purpose in the implemented pipeline |
|---|---|
| Python ingestion and source validation | Downloads the six TLC Parquet files and zone CSV when absent; scans existing files for readable content and required schema before reuse. A changed checksum against the existing manifest stops the run. |
| Raw storage and source manifest | `data/raw/` retains source bytes. `source_manifest.json` records URLs, row counts, sizes and SHA-256 checksums for traceability and reconciliation. |
| Python profiling | Produces descriptive raw-data profiles before the analytical quality rules are applied. |
| Prefect orchestration | Runs source validation, profiling, dbt, candidate checks and publication in order, with task logs and failures. |
| dbt staging and quality classification | The two staging models expose typed trip and zone inputs as views. `int_trip_quality` is a table that classifies each physical trip row and records quality and financial flags. |
| dbt dimensions, fact and marts | Tables persist accepted `fact_trips`, `rejected_trips`, three dimensions and four tested analytical summaries. Tests check keys, partitioning and metric reconciliation. |
| DuckDB candidate warehouse and publication | dbt builds a separate candidate file. The pipeline checks its required tables, row reconciliation and IDs, checkpoints it, then replaces the published file only after success. |
| Streamlit and Plotly | Serve interactive KPIs and charts with pickup-date and borough filters. The dashboard reads `fact_trips` for metrics and `dim_payment_type` for payment labels. |
| Docker Compose | Builds the pinned Python environment, mounts local data, runs the pipeline and serves the dashboard in separate services. |

Staging uses views so typed source access does not duplicate the raw data in
the warehouse. Intermediate and mart models use tables so their classified
rows and analytical outputs are persisted for downstream tests and queries.

## Analytical data model

The warehouse uses a fact-and-dimension design:

- `fact_trips`: one accepted physical Parquet source row per record,
  enriched with locations, derived fields and quality indicators.
- `rejected_trips`: excluded records with a clear rejection reason.
- `dim_date`, `dim_zone`, `dim_payment_type`: reusable descriptive
  dimensions for analytical queries.
- `mart_daily_performance`: daily activity, charges and average metrics.
- `mart_hourly_demand`: trip activity by weekday and pickup hour.
- `mart_zone_performance`: trip and charge summaries by pickup zone.
- `mart_payment_summary`: trip and financial metrics by payment method.

The dashboard currently queries filtered `fact_trips` directly for its
KPIs and charts and joins `dim_payment_type` for payment labels. The marts
are tested, reusable analytical outputs; the dashboard does not read them.
The current marts do not all carry the date and borough detail needed to
answer every dashboard filter combination.

Stable trip IDs use source filename plus physical row number. This keeps
identical-content source records separate while preserving traceability.

## Pipeline

1. Download the trip records and taxi-zone lookup.
2. Preserve the original files in data/raw.
3. Generate a data-profiling report.
4. Build staging models and apply documented quality rules.
5. Create accepted and rejected trip tables.
6. Build dimensions and analytical summaries.
7. Run dbt tests and warehouse checks against a candidate DuckDB file.
8. Publish the candidate only after every check succeeds.
9. Display results through the dashboard.

## Project folders

- ingestion/: download and profiling scripts
- orchestration/: Prefect pipeline
- transformations/: dbt models, configuration and tests
- dashboard/: Streamlit application
- docs/: profiling report and cleaning rules
- data/raw/: downloaded source files
- data/warehouse/: generated DuckDB database
- data/rejected/: reserved for optional rejected-record exports

Rejected records currently remain in the warehouse's
rejected_trips table.

## Requirements

Install Git and Docker Desktop. The image uses Python 3.11.14 and
the versions pinned in requirements.txt.
Keep Docker Desktop running when executing the commands below.

A separate local Python environment is not required for Docker.

Recommended local resources for the verified six-month build:

- Approximately 10 GB of free disk space for source, candidate and
  published warehouse files during processing
- At least 8 GB assigned to Docker Desktop
- Stable internet access for the first source download

The measured local-source rebuild and its environment are recorded in
`docs/verification/benchmark-2026-11-07.md`. A first run also needs source
downloads and an image build, which that benchmark did not include.

## Capacity and scaling

By default the pipeline rebuilds the selected January-June 2025 dataset on
each run. New months can also be loaded one at a time (see "Incremental
monthly batches" below). The measured rebuild, machine and resource limits are documented
in `docs/verification/benchmark-2026-11-07.md`; those observations establish
sufficiency only for this tested six-month workload and environment.

For several years, future incremental processing could validate new or
changed source files and rebuild affected outputs while preserving stable
row identity, exact source reconciliation and safe publication. Dashboard
summaries would need enough date and borough detail to keep combined filters
correct. Distributed processing such as Spark should be evaluated if
measured runtime, memory, storage or workload needs exceed practical
single-machine capacity. Several years alone do not establish that need;
the six-month timings cannot guarantee performance at a larger size.

## Run the pipeline

Clone the repository and open a terminal in its root folder,
where docker-compose.yml is located.

Build the images and run:

```bash
docker compose build pipeline dashboard
docker compose run --rm pipeline python tests/synthetic_fixture.py
docker compose stop dashboard
docker compose run --rm pipeline
docker compose run --rm pipeline python -m unittest discover -s tests -p "test_*.py"
docker compose run --rm pipeline python tests/verify_warehouse.py
```

The first build installs dependencies and may take several minutes.
Wait for the pipeline to complete successfully.
The synthetic fixture builds into a temporary database and uses no real TLC
download. Stop the dashboard before publishing the new warehouse, including
on Windows. The focused Python tests and warehouse verification run against
the completed published warehouse. `dbt build` writes its full results to
`data/verification/dbt-target/run_results.json` and its logs to
`data/verification/dbt-logs/`; both remain local and are ignored by Git.

## Start the dashboard

After the pipeline succeeds, run:

```bash
docker compose up -d dashboard
```

Open http://localhost:8501 in your browser.

Use the pickup-date range and pickup-borough filters
to explore the results. The sidebar's Reset filters button returns to
the full six-month period and all boroughs. Recorded charges may be displayed in
millions when large; the KPI help tooltip shows the exact amount.

## Rebuild after changes

Stop the dashboard before updating the warehouse:

```bash
docker compose stop dashboard
```

Rebuild the images and run the pipeline:

```bash
docker compose build pipeline dashboard
docker compose run --rm pipeline
```

Only after it succeeds, restart the dashboard:

```bash
docker compose up -d dashboard
```

The Docker images contain copies of the source code, so rebuild
the relevant service after changing its code.
The pipeline builds data/warehouse/nyc_taxi_candidate.duckdb,
closes and checkpoints it, then replaces the published file. A failed
build or test leaves nyc_taxi.duckdb intact. A Windows program (outside
Docker) that holds the DuckDB file open can block the replacement; the
pipeline retries for about two minutes, then fails safely with the live
file unchanged (see the Windows note under "Monthly schedule"). Stopping
the dashboard first remains the simplest routine. If a run crashes, check that no pipeline is
running before removing data/warehouse/.pipeline.lock. Rerun the
pipeline to discard its incomplete candidate. dbt build itself is
not an all-or-nothing transaction.
Running dbt directly targets the candidate file; only the Prefect
pipeline validates and publishes it.

## Stop the services

```bash
docker compose down
```

The local data files remain in the project's data folder.

## Incremental monthly batches

NYC TLC publishes one Parquet file per month, so the batch unit is one
monthly file. The pipeline has two modes:

| Mode | What it does |
|---|---|
| `full` (default) | Rebuilds every month from `PERIOD_START` to `PERIOD_END` into a fresh candidate. With no settings this is exactly the January-June 2025 build. |
| `incremental` | Finds the last loaded month in the `pipeline_batches` table and loads only the next calendar month, if TLC has published it. It never skips ahead, so months always load in order with no gaps. |

| Variable | Default | Meaning |
|---|---|---|
| `PIPELINE_MODE` | `full` | `full` or `incremental` |
| `PERIOD_START`, `PERIOD_END` | `2025-01`, `2025-06` | Inclusive months for a full rebuild |
| `MAX_MONTH` | none | Incremental mode never loads a month after this (`YYYY-MM`) |
| `PIPELINE_BATCH_MONTH` | none | Explicitly reprocess an already loaded month (`YYYY-MM`) |
| `PIPELINE_SCHEDULE_CRON`, `PIPELINE_SCHEDULE_TZ` | `0 6 2 * *`, `UTC` | Monthly schedule (06:00 on the 2nd) |

Incremental mode needs a warehouse that already has the `pipeline_batches`
log, so run one full rebuild first. Then check for new data:

```bash
docker compose stop dashboard
docker compose run --rm -e PIPELINE_MODE=incremental pipeline
docker compose up -d dashboard
```

The check works like this:

- The next file's URL is predictable
  (`https://d37ci6vzurychx.cloudfront.net/trip-data/yellow_tripdata_YYYY-MM.parquet`).
  The pipeline sends one lightweight HEAD request for it.
- HTTP 403/404 means the month is not published yet. The run logs
  "No new data" and ends successfully without changing anything.
- Timeouts and other errors fail the run after the usual task retries.
- A published file is downloaded through the normal validated path (a
  `.part` file, schema and row checks, quarantine of bad files, SHA-256).
  It is then added to `data/raw/source_manifest.json`.
- Every already loaded file must still match its recorded checksum. An
  unexpected change stops the run; changed files are never reloaded
  silently.

How a batch is applied:

1. The live warehouse is copied to the candidate.
2. The project period is extended to the end of the new month.
3. dbt reclassifies only the new file's rows plus rows from any loaded file
   whose pickup falls in the new month. An example is a 1 July pickup
   recorded in the June file: it was rejected as outside the period and is
   now accepted. These are the only rows whose classification can change.
4. `fact_trips` and `rejected_trips` are incremental dbt models. Each
   reclassified `trip_id` is removed from both tables before the new
   classification is inserted, so rows are never duplicated and rerunning a
   batch changes nothing.
5. Dimensions and marts are rebuilt from `fact_trips`.
6. All dbt tests and the candidate checks run over all loaded files. The
   checks cover source rows = accepted + rejected per file, agreement
   between the batch log and the manifest, and contiguous months.
7. Only then is the candidate published, using the same checkpoint and
   atomic replace as a full rebuild. A failed batch leaves the live
   warehouse and batch log unchanged.

Incremental loading therefore ends in the same state as a full rebuild of
the same months. `tests/synthetic_incremental_fixture.py` checks this after
every batch. In incremental mode, `int_trip_quality` holds only that run's
reclassified rows. Each batch is profiled to the ignored
`data/profiles/data_profile_YYYY-MM.md`; the submitted January-June
profile is only written by a default full rebuild.

The batch log `pipeline_batches` has one row per month with:

- file name, source URL and SHA-256
- source, accepted and rejected row counts
- status, load mode and processed-at UTC time

The dashboard shows the loaded month range and the last processed time
from this table. Its collapsed "Data pipeline status" panel, at the bottom
of the page, lists each loaded month with source, accepted and rejected
rows, whether they reconcile, and the processed-at time. The panel only
reads the table and ignores the date and borough filters.

### Monthly schedule

Prefect serves the flow in incremental mode on a cron schedule. The
optional `scheduler` service is under a Compose profile, so it never
starts with the default commands:

```bash
docker compose --profile schedule up -d scheduler
docker compose --profile schedule logs -f scheduler
docker compose --profile schedule stop scheduler
```

The service runs a local Prefect server in its container. Its database
(the deployment, schedule and run history) is kept in the named Docker
volume `prefect-home`, so restarts don't lose it. `docker compose down -v`
deletes that volume.

**Prefect UI.** Once the logs show "being served", open
http://localhost:4200 in your browser:

- **Deployments → `monthly-incremental-batches`:** the monthly cron
  schedule (default `0 6 2 * *`, 06:00 UTC on the 2nd) and the upcoming
  scheduled runs.
- **Flow Runs:** run history with each run's state and logs. "No new data"
  is a normal, successful outcome.
- **Run now:** on the deployment page, choose **Run → Quick run**. From a
  terminal:

  ```bash
  docker compose --profile schedule exec -e PREFECT_API_URL=http://127.0.0.1:4200/api scheduler prefect deployment run "NYC Taxi End-to-End Pipeline/monthly-incremental-batches"
  ```

  A manual run does the same as a scheduled one. It checks TLC for the
  next month and, if that file is published, downloads it and updates the
  live warehouse.

On restart, Prefect pauses the deployment's schedule while the service is
stopping. When the service starts again, it re-registers the deployment and
regenerates the upcoming scheduled runs within about a minute. Completed run
history is kept.

**Windows note (tested 13 Nov 2026 on Docker Desktop for Windows).**

What is handled:

- The Docker `dashboard` service does **not** block publication. A
  scheduled or manual run can publish while it is running, whether it is
  idle or holding a read-only connection open. A full rebuild published
  normally with the dashboard up, and its next query showed the new data.
- If the warehouse file is briefly held by a Windows program, the final
  replace is retried for about two minutes (waits of 2, 4, 8, 15, 30, 30
  and 30 s). Examples are a file scanner or a quick query from a tool
  running directly on Windows. Each attempt is logged.

What still needs action: a Windows program that keeps the file open for
longer still blocks publication. Examples are a Streamlit dashboard,
DuckDB client or Python session started outside Docker. The run then
fails with "Publication blocked". The live warehouse is unchanged and the
tested candidate is kept. Close that program and start the run again with
**Run** or the command above.

Stopping the Docker dashboard around a run is no longer needed for
publication. It is still harmless.

### Confirm a full rebuild still matches the submitted numbers

```bash
docker compose stop dashboard
docker compose run --rm pipeline
docker compose run --rm pipeline python tests/verify_warehouse.py
docker compose run --rm pipeline python -c "import duckdb; db = duckdb.connect('data/warehouse/nyc_taxi.duckdb', read_only=True); [print(r) for r in db.execute('select month, source_rows, accepted_rows, rejected_rows from pipeline_batches order by month').fetchall()]"
```

Expected results:

- Totals: 23,886,241 accepted rows, 197,143 rejected rows, 22,560,818
  eligible rows, $637,824,068.09 recorded charges and 181 daily rows.
- Per-month counts equal to `docs/verification/summary.md`.
- dbt reports 12 models and 43 tests passing.

## Verification evidence

The October verification is in `docs/verification/summary.md` and
`details.json`. The separate November controlled rebuild is in
`docs/verification/benchmark-2026-11-07.md` and its JSON companion. Each
records its revision scope; the starting commit alone does not identify a
modified working tree. Full logs and generated dbt artifacts remain under
ignored `data/verification/` for independent review. See
`docs/verification/README.md` for the commands and evidence scope.

## Data-quality and metric definitions

- Raw source files are preserved unchanged.
- Existing source files are checked for schema and readability. An
  unusable file is renamed with an .invalid timestamp before a fresh
  download. data/raw/source_manifest.json records names, row counts,
  byte sizes, source URLs and SHA-256 checksums. Individual bad trip
  rows are classified by dbt rather than treated as source failure.
- The fact-table grain is one physical Parquet source row. trip_id is
  based on source filename and file row number, so it remains stable
  while the source bytes and name remain the same. A content fingerprint
  identifies identical records; duplicates remain separate accepted or
  rejected rows and are never silently dropped.
- Invalid records are retained in rejected_trips with a reason.
- Unusual records may be retained with quality flags.
- Records with missing or negative fare or total amounts are
  excluded from standard dashboard metrics.
- Missing financial amounts are not replaced with zero.
- Recorded charges represent passenger charges, not profit.
- Cash tips are not captured in the source tip field.
- Payment code 0 is labeled "Flex Fare trip".
- Average distance excludes zero-distance trips and trips
  exceeding 100 miles.
- Average duration excludes trips exceeding six hours.
- Trip duration is calculated in seconds divided by 60.
- The profiling report describes raw rows with ordered timestamps and
  nonnegative distance, fare, and total amounts. Its averages do not apply
  the dashboard's project-period, location, financial-eligibility, and
  metric-specific filters and therefore can differ from dashboard KPIs.
- Trips measure recorded activity, not unmet taxi demand.

See docs/cleaning_rules.md for the detailed rules.

## Tests

The pipeline runs dbt build, which builds models and runs tests.

Checks include:
- Required values and unique dimension keys
- Valid timestamps and January-June date scope
- No negative distances in accepted trips
- Rejection reasons for rejected records
- Source count equals accepted plus rejected counts
- Correct missing-financial and adjustment flags
- Source IDs appear exactly once across accepted and rejected outputs
- Daily, hourly, zone and payment counts and charges reconcile to
  eligible fact rows, with a $0.01 tolerance for floating-point totals

Passing tests confirms the implemented checks; it does not
guarantee that every source value is accurate.

## Verified results and initial findings

The final January-June 2025 build produced:

- 24,083,384 source rows
- 23,886,241 accepted trips
- 197,143 rejected trips
- 22,560,818 financially eligible trips
- 181 daily summary rows
- $637,824,068.09 in eligible recorded passenger charges
- 12 successful dbt model builds, 43 passing dbt data tests, and 11 passing
  focused Python tests

Initial dashboard findings include:

- Eligible recorded trips increased from 3.33 million in January to a
  high of 4.20 million in May.
- May also had the highest monthly eligible recorded charges at
  approximately $123.32 million.
- Pickup hour 18:00 had the largest six-month trip count.
- Upper East Side South was the leading pickup zone by trip count.
- The highest single-day eligible trip count was 163,855 on 17 May 2025.

These are descriptive findings from recorded trips and should not be
interpreted as causal explanations or measurements of unmet demand.

## Collaboration

Both members use the same repository and maintain their own
local datasets and database.

Use separate branches for changes and review pull requests
before merging.

Do not commit datasets, databases, Python environments,
passwords, .env files or generated dbt output.

## Remaining work

- Complete the final report and presentation.

## Data source

NYC Taxi and Limousine Commission:
https://www.nyc.gov/site/tlc/about/tlc-trip-record-data.page
