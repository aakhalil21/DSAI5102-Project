# NYC Taxi Demand and Fare Analytics Pipeline

DSAI5102 end-to-end batch data pipeline using NYC Yellow Taxi
Trip Records and the official Taxi Zone Lookup Table.

## Current scope

The pipeline processes January 2025.

## Tools

- Python: downloading and profiling data
- Prefect: pipeline orchestration
- dbt: SQL transformations and data-quality tests
- DuckDB: analytical warehouse
- Streamlit and Plotly: interactive dashboard
- Docker Compose: running the project
- GitHub: team collaboration and version control

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

## Run the pipeline

Clone the repository and open a terminal in its root folder,
where docker-compose.yml is located.

Build the images and run:

```bash
docker compose build pipeline dashboard
docker compose run --rm pipeline
```

The first build installs dependencies and may take several minutes.
Wait for the pipeline to complete successfully.

## Start the dashboard

After the pipeline succeeds, run:

```bash
docker compose up -d dashboard
```

Open http://localhost:8501 in your browser.

Use the pickup-date range and pickup-borough filters
to explore the results. The sidebar's Reset filters button returns to
the full month and all boroughs. Recorded charges may be displayed in
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
build or test leaves nyc_taxi.duckdb intact. Keep the dashboard stopped
during publication, especially on Windows, where an open DuckDB file
can block replacement. If a run crashes, check that no pipeline is
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
  and duplicate flag identify identical records; duplicates remain
  separate accepted or rejected rows and are never silently dropped.
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
- Trips measure recorded activity, not unmet taxi demand.

See docs/cleaning_rules.md for the detailed rules.

## Tests

The pipeline runs dbt build, which builds models and runs tests.

Checks include:
- Required values and unique dimension keys
- Valid timestamps and January date scope
- No negative distances in accepted trips
- Rejection reasons for rejected records
- Source count equals accepted plus rejected counts
- Correct missing-financial and adjustment flags
- Source IDs appear exactly once across accepted and rejected outputs
- Daily, hourly, zone and payment counts and charges reconcile to
  eligible fact rows, with a $0.01 tolerance for floating-point totals

Passing tests confirms the implemented checks; it does not
guarantee that every source value is accurate.

## Collaboration

Both members use the same repository and maintain their own
local datasets and database.

Use separate branches for changes and review pull requests
before merging.

Do not commit datasets, databases, Python environments,
passwords, .env files or generated dbt output.

## Remaining work

- Add congestion-fee and fare/trip relationship analysis.
- Complete the report and presentation.

## Data source

NYC Taxi and Limousine Commission:
https://www.nyc.gov/site/tlc/about/tlc-trip-record-data.page
