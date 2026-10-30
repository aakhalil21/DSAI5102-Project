from pathlib import Path

import duckdb


PROJECT_ROOT = Path(__file__).resolve().parents[1]

TRIP_FILE_GLOB = (
    PROJECT_ROOT
    / "data"
    / "raw"
    / "yellow_tripdata_2025-0[1-6].parquet"
)

ZONE_FILE = (
    PROJECT_ROOT
    / "data"
    / "raw"
    / "taxi_zone_lookup.csv"
)

REPORT_FILE = (
    PROJECT_ROOT
    / "docs"
    / "data_profile_january_june_2025.md"
)


def make_sql_path(path):
    """Prepare a file path for use inside SQL."""

    return str(path).replace("'", "''")


def format_value(value):
    """Format numbers for the report."""

    if value is None:
        return "N/A"

    if isinstance(value, float):
        return "{:,.2f}".format(value)

    return "{:,}".format(value)


def main():
    """Profile the January-June 2025 taxi data."""

    if len(list((PROJECT_ROOT / "data" / "raw").glob("yellow_tripdata_2025-0[1-6].parquet"))) != 6:
        raise FileNotFoundError(
            "All six monthly trip files are required"
        )

    if not ZONE_FILE.exists():
        raise FileNotFoundError(
            "Zone file not found: {}".format(ZONE_FILE)
        )

    trip_path = make_sql_path(TRIP_FILE_GLOB)
    zone_path = make_sql_path(ZONE_FILE)

    connection = duckdb.connect()

    connection.execute(
        """
        CREATE VIEW raw_trips AS
        SELECT *
        FROM read_parquet('{}')
        """.format(trip_path)
    )

    connection.execute(
        """
        CREATE VIEW taxi_zones AS
        SELECT *
        FROM read_csv_auto(
            '{}',
            header = true
        )
        """.format(zone_path)
    )

    schema = connection.execute(
        """
        DESCRIBE raw_trips
        """
    ).fetchall()

    summary = connection.execute(
        """
        SELECT
            COUNT(*) AS total_rows,
            MIN(tpep_pickup_datetime),
            MAX(tpep_pickup_datetime),
            MIN(tpep_dropoff_datetime),
            MAX(tpep_dropoff_datetime),
            COUNT(DISTINCT PULocationID),
            COUNT(DISTINCT DOLocationID)
        FROM raw_trips
        """
    ).fetchone()

    quality = connection.execute(
        """
        SELECT
            COUNT_IF(
                tpep_pickup_datetime IS NULL
            ),
            COUNT_IF(
                tpep_dropoff_datetime IS NULL
            ),
            COUNT_IF(
                passenger_count IS NULL
            ),
            COUNT_IF(
                PULocationID IS NULL
            ),
            COUNT_IF(
                DOLocationID IS NULL
            ),
            COUNT_IF(
                tpep_dropoff_datetime
                <= tpep_pickup_datetime
            ),
            COUNT_IF(
                trip_distance < 0
            ),
            COUNT_IF(
                trip_distance = 0
            ),
            COUNT_IF(
                fare_amount < 0
            ),
            COUNT_IF(
                total_amount < 0
            ),
            COUNT_IF(
                passenger_count < 0
            ),
            COUNT_IF(
                passenger_count > 8
            ),
            COUNT_IF(
                trip_distance > 100
            ),
            COUNT_IF(
                DATE_DIFF(
                    'second',
                    tpep_pickup_datetime,
                    tpep_dropoff_datetime
                ) > 21600
            ),
            COUNT_IF(
                tpep_pickup_datetime
                    < TIMESTAMP '2025-01-01'
                OR
                tpep_pickup_datetime
                    >= TIMESTAMP '2025-07-01'
            )
        FROM raw_trips
        """
    ).fetchone()

    unmatched = connection.execute(
        """
        SELECT
            COUNT_IF(
                pickup.LocationID IS NULL
            ),
            COUNT_IF(
                dropoff.LocationID IS NULL
            )
        FROM raw_trips AS trips

        LEFT JOIN taxi_zones AS pickup
            ON trips.PULocationID
            = pickup.LocationID

        LEFT JOIN taxi_zones AS dropoff
            ON trips.DOLocationID
            = dropoff.LocationID
        """
    ).fetchone()

    averages = connection.execute(
        """
        SELECT
            AVG(trip_distance),
            AVG(fare_amount),
            AVG(total_amount),
            AVG(
                DATE_DIFF(
                    'second',
                    tpep_pickup_datetime,
                    tpep_dropoff_datetime
                ) / 60.0
            )
        FROM raw_trips
        WHERE
            tpep_dropoff_datetime
                > tpep_pickup_datetime
            AND trip_distance >= 0
            AND fare_amount >= 0
            AND total_amount >= 0
        """
    ).fetchone()

    labels = [
        "Missing pickup timestamps",
        "Missing drop-off timestamps",
        "Missing passenger counts",
        "Missing pickup zone IDs",
        "Missing drop-off zone IDs",
        "Drop-off not later than pickup",
        "Negative trip distances",
        "Zero trip distances",
        "Negative fare amounts",
        "Negative total amounts",
        "Negative passenger counts",
        "Passenger counts above 8",
        "Trip distances above 100 miles",
        "Trips lasting more than 6 hours",
        "Pickup timestamps outside January-June 2025",
    ]

    report = []

    report.append(
        "# January-June 2025 Yellow Taxi Data Profile"
    )
    report.append("")
    report.append("## Dataset summary")
    report.append("")
    report.append(
        "- Total rows: {}".format(
            format_value(summary[0])
        )
    )
    report.append(
        "- Earliest pickup: {}".format(summary[1])
    )
    report.append(
        "- Latest pickup: {}".format(summary[2])
    )
    report.append(
        "- Earliest drop-off: {}".format(summary[3])
    )
    report.append(
        "- Latest drop-off: {}".format(summary[4])
    )
    report.append(
        "- Distinct pickup location IDs: {}".format(
            format_value(summary[5])
        )
    )
    report.append(
        "- Distinct drop-off location IDs: {}".format(
            format_value(summary[6])
        )
    )

    report.append("")
    report.append("## Schema")
    report.append("")
    report.append("| Column | Data type | Nullable |")
    report.append("|---|---|---|")

    for row in schema:
        report.append(
            "| {} | {} | {} |".format(
                row[0],
                row[1],
                row[2],
            )
        )

    report.append("")
    report.append("## Data-quality findings")
    report.append("")
    report.append("| Check | Affected rows |")
    report.append("|---|---:|")

    for label, value in zip(labels, quality):
        report.append(
            "| {} | {} |".format(
                label,
                format_value(value),
            )
        )

    report.append(
        "| Pickup zones absent from lookup | {} |".format(
            format_value(unmatched[0])
        )
    )

    report.append(
        "| Drop-off zones absent from lookup | {} |".format(
            format_value(unmatched[1])
        )
    )

    report.append("")
    report.append("## Initial averages")
    report.append("")
    report.append(
        "- Average distance: {} miles".format(
            format_value(averages[0])
        )
    )
    report.append(
        "- Average fare: ${}".format(
            format_value(averages[1])
        )
    )
    report.append(
        "- Average total amount: ${}".format(
            format_value(averages[2])
        )
    )
    report.append(
        "- Average duration: {} minutes".format(
            format_value(averages[3])
        )
    )

    report.append("")
    report.append("## Notes")
    report.append("")
    report.append(
        "These averages describe raw rows with ordered timestamps, "
        "non-negative distance, fare, and total amounts. They are not "
        "dashboard KPIs: the dashboard applies project-period, location, "
        "financial-eligibility, and metric-specific filters to accepted trips."
    )

    REPORT_FILE.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    REPORT_FILE.write_text(
        "\n".join(report) + "\n",
        encoding="utf-8",
    )

    connection.close()

    print("Data profiling completed successfully.")
    print("Report created at:")
    print(REPORT_FILE)


if __name__ == "__main__":
    main()
