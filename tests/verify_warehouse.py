"""Print a stable January warehouse signature and check dashboard filters."""

import json
from pathlib import Path

import duckdb


DATABASE = Path(__file__).resolve().parents[1] / "data" / "warehouse" / "nyc_taxi.duckdb"
with duckdb.connect(str(DATABASE), read_only=True) as db:
    row = db.execute("""
        select count(*), sum(hash(trip_id)),
            count(*) filter (where not is_financial_adjustment and not is_financial_data_missing),
            sum(total_amount) filter (where not is_financial_adjustment and not is_financial_data_missing)
        from main.fact_trips
    """).fetchone()
    rejected = db.execute("select count(*), sum(hash(trip_id)) from main.rejected_trips").fetchone()
    first_date, last_date = db.execute(
        "select min(pickup_date), max(pickup_date) from main.fact_trips"
    ).fetchone()
    borough = db.execute(
        "select pickup_borough from main.fact_trips where pickup_borough is not null limit 1"
    ).fetchone()[0]
    eligible = "not is_financial_adjustment and not is_financial_data_missing"
    one_day = db.execute(
        f"select count(*) from main.fact_trips where {eligible} and pickup_date = ?",
        [first_date],
    ).fetchone()[0]
    period = db.execute(
        f"select count(*) from main.fact_trips where {eligible} and pickup_date between ? and ?",
        [first_date, last_date],
    ).fetchone()[0]
    filtered = db.execute(
        f"select count(*) from main.fact_trips where {eligible} and pickup_date between ? and ? and pickup_borough = ?",
        [first_date, last_date, borough],
    ).fetchone()[0]
    assert 0 < one_day <= period and 0 < filtered <= period
    print(json.dumps({
        "accepted_rows": row[0], "accepted_id_hash_sum": row[1],
        "eligible_rows": row[2], "eligible_recorded_charges": row[3],
        "rejected_rows": rejected[0], "rejected_id_hash_sum": rejected[1],
        "daily_rows": db.execute("select count(*) from main.mart_daily_performance").fetchone()[0],
        "one_day_rows": one_day, "period_rows": period,
        "borough": borough, "borough_rows": filtered,
    }, sort_keys=True))
