# NYC Taxi Demand and Fare Analytics Pipeline

DSAI5102 end-to-end batch data pipeline using NYC Yellow Taxi
Trip Records and the official Taxi Zone Lookup Table.

## Current scope

The pipeline currently processes January 2025.
The planned final scope is January-June 2025.

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
7. Run dbt tests and warehouse checks.
8. Display results through the dashboard.

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

Install Git and Docker Desktop.
Keep Docker Desktop running when executing the commands below.

A separate local Python environment is not required for Docker.

## Run the pipeline

Clone the repository and open a terminal in its root folder,
where docker-compose.yml is located.

Run:

```bash
docker compose run --build --rm pipeline
```

The first build installs dependencies and may take several minutes.
Wait for the pipeline to complete successfully.

## Start the dashboard

After the pipeline succeeds, run:

```bash
docker compose up --build -d dashboard
```

Open http://localhost:8501 in your browser.

Use the pickup-date range and pickup-borough filters
to explore the results.

## Rebuild after changes

Stop the dashboard before updating the warehouse:

```bash
docker compose stop dashboard
```

Rebuild and run the pipeline:

```bash
docker compose run --build --rm pipeline
```

Only after it succeeds, rebuild and start the dashboard:

```bash
docker compose up --build -d dashboard
```

The Docker images contain copies of the source code, so rebuild
the relevant service after changing its code.

## Stop the services

```bash
docker compose down
```

The local data files remain in the project's data folder.

## Data-quality and metric definitions

- Raw source files are preserved unchanged.
- Invalid records are retained in rejected_trips with a reason.
- Unusual records may be retained with quality flags.
- Records with missing or negative fare or total amounts are
  excluded from standard dashboard metrics.
- Missing financial amounts are not replaced with zero.
- Recorded charges represent passenger charges, not profit.
- Cash tips are not captured in the source tip field.
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

- Expand the pipeline to January-June 2025.
- Strengthen source-file validation and duplicate handling.
- Protect the last successful warehouse if a build fails.
- Add congestion-fee and fare/trip relationship analysis.
- Complete the report and presentation.

## Data source

NYC Taxi and Limousine Commission:
https://www.nyc.gov/site/tlc/about/tlc-trip-record-data.page