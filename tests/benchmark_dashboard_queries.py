"""Time two exact dashboard SQL queries outside Streamlit's browser/cache path."""

import argparse
import ast
from datetime import date, datetime, timezone
import json
from pathlib import Path
import statistics
import time

import duckdb


ROOT = Path.cwd()
APP = ROOT / "dashboard" / "app.py"
WAREHOUSE = ROOT / "data" / "warehouse" / "nyc_taxi.duckdb"


def query_template(name):
    tree = ast.parse(APP.read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(
            isinstance(target, ast.Name) and target.id == name for target in node.targets
        ):
            query = node.value.args[0]
            return ast.literal_eval(query.func.value)
    raise ValueError(f"Dashboard query not found: {name}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    templates = {name: query_template(name) for name in ("metrics", "daily_data")}
    scenarios = {
        "full_period_all_boroughs": (date(2025, 1, 1), date(2025, 6, 30), None),
        "full_period_manhattan": (date(2025, 1, 1), date(2025, 6, 30), "Manhattan"),
        "cross_month_all_boroughs": (date(2025, 3, 15), date(2025, 5, 15), None),
    }
    results = {}
    for scenario, (first, last, borough) in scenarios.items():
        where = "pickup_date between ? and ? and (not is_financial_adjustment and not is_financial_data_missing)"
        params = [first, last]
        if borough:
            where += " and pickup_borough = ?"
            params.append(borough)
        results[scenario] = {}
        for name, template in templates.items():
            sql = template.format(where)
            repetitions = []
            for _ in range(3):
                started = time.perf_counter()
                with duckdb.connect(str(WAREHOUSE), read_only=True) as connection:
                    data = connection.execute(sql, params).fetchdf()
                repetitions.append(round(time.perf_counter() - started, 4))
            results[scenario][name] = {
                "seconds": repetitions,
                "median_seconds": round(statistics.median(repetitions), 4),
                "result_rows": len(data),
                "total_trips": int(data.iloc[0]["total_trips"]) if name == "metrics" else int(data["trip_count"].sum()),
            }
    report = {
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "scope": "Exact metrics and daily_data SQL templates extracted from dashboard/app.py; new read-only DuckDB connection and fetchdf per repetition; no Streamlit, cache, Plotly, network, or browser rendering",
        "clock": "time.perf_counter",
        "repetitions_per_query_scenario": 3,
        "results": results,
    }
    Path(args.output).write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
