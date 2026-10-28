from pathlib import Path
import shutil
import subprocess
import sys

import duckdb
from prefect import flow, get_run_logger, task


PROJECT_ROOT = Path(__file__).resolve().parents[1]
TRANSFORMATIONS_DIR = PROJECT_ROOT / "transformations"

DOWNLOAD_SCRIPT = (
    PROJECT_ROOT
    / "ingestion"
    / "download_data.py"
)

PROFILE_SCRIPT = (
    PROJECT_ROOT
    / "ingestion"
    / "profile_data.py"
)

WAREHOUSE_FILE = (
    PROJECT_ROOT
    / "data"
    / "warehouse"
    / "nyc_taxi.duckdb"
)


def execute_command(command, working_directory):
    """Run a command and fail if the command is unsuccessful."""

    result = subprocess.run(
        command,
        cwd=str(working_directory),
        check=True,
        text=True,
    )

    return result.returncode


@task(
    name="Download raw taxi data",
    retries=2,
    retry_delay_seconds=10,
)
def download_raw_data():
    """Run the idempotent data downloader."""

    logger = get_run_logger()
    logger.info("Starting raw-data ingestion.")

    execute_command(
        [
            sys.executable,
            str(DOWNLOAD_SCRIPT),
        ],
        PROJECT_ROOT,
    )

    logger.info("Raw-data ingestion completed.")


@task(
    name="Profile raw taxi data",
    retries=1,
    retry_delay_seconds=5,
)
def profile_raw_data():
    """Generate the raw-data quality report."""

    logger = get_run_logger()
    logger.info("Starting raw-data profiling.")

    execute_command(
        [
            sys.executable,
            str(PROFILE_SCRIPT),
        ],
        PROJECT_ROOT,
    )

    logger.info("Raw-data profiling completed.")


@task(
    name="Build and test dbt models",
    retries=1,
    retry_delay_seconds=5,
)
def build_dbt_models():
    """Build all dbt models and execute their tests."""

    logger = get_run_logger()

    dbt_executable = shutil.which("dbt")

    if dbt_executable is None:
        raise RuntimeError(
            "The dbt executable was not found."
        )
    WAREHOUSE_FILE.parent.mkdir(parents=True, exist_ok=True)
    logger.info("Starting dbt build.")

    execute_command(
        [
            dbt_executable,
            "build",
            "--profiles-dir",
            ".",
        ],
        TRANSFORMATIONS_DIR,
    )

    logger.info("dbt build completed successfully.")


@task(name="Validate analytical warehouse")
def validate_warehouse():
    """Verify that the expected warehouse tables exist."""

    logger = get_run_logger()

    if not WAREHOUSE_FILE.exists():
        raise FileNotFoundError(
            "Warehouse file not found: {}".format(
                WAREHOUSE_FILE
            )
        )

    connection = duckdb.connect(
        str(WAREHOUSE_FILE),
        read_only=True,
    )

    required_tables = [
        "fact_trips",
        "rejected_trips",
        "dim_date",
        "dim_zone",
        "dim_payment_type",
        "mart_daily_performance",
        "mart_hourly_demand",
        "mart_zone_performance",
        "mart_payment_summary",
    ]

    table_rows = connection.execute(
        """
        select table_name
        from information_schema.tables
        where table_schema = 'main'
        """
    ).fetchall()

    available_tables = {
        row[0] for row in table_rows
    }

    missing_tables = [
        table_name
        for table_name in required_tables
        if table_name not in available_tables
    ]

    if missing_tables:
        connection.close()

        raise RuntimeError(
            "Missing warehouse tables: {}".format(
                ", ".join(missing_tables)
            )
        )

    fact_count = connection.execute(
        """
        select count(*)
        from main.fact_trips
        """
    ).fetchone()[0]

    rejected_count = connection.execute(
        """
        select count(*)
        from main.rejected_trips
        """
    ).fetchone()[0]

    daily_count = connection.execute(
        """
        select count(*)
        from main.mart_daily_performance
        """
    ).fetchone()[0]

    connection.close()

    logger.info(
        "Accepted fact rows: {:,}".format(
            fact_count
        )
    )

    logger.info(
        "Rejected rows: {:,}".format(
            rejected_count
        )
    )

    logger.info(
        "Daily summary rows: {:,}".format(
            daily_count
        )
    )

    return {
        "fact_rows": fact_count,
        "rejected_rows": rejected_count,
        "daily_rows": daily_count,
    }


@flow(
    name="NYC Taxi End-to-End Pipeline",
    log_prints=True,
)
def nyc_taxi_pipeline():
    """Run the complete local batch pipeline."""

    download_raw_data()
    profile_raw_data()
    build_dbt_models()
    validation_result = validate_warehouse()

    print("Pipeline completed successfully.")
    print(validation_result)


if __name__ == "__main__":
    nyc_taxi_pipeline()
