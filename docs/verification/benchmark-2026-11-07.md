# Six-month controlled rebuild: 7 November 2026

This is **one full January-June 2025 rebuild using validated local source
files**, not a fresh-clone or cold-download benchmark. The pipeline log shows
six existing Parquet files and the zone CSV validated; zero downloads.
Historical October results in `summary.md` and `details.json` belong to an
earlier source fingerprint and remain unchanged.

## Revision and environment

The run started from clean commit `c923aaa77cfa0155c3a79ccddac4244fd3abac97`
on branch `docs/six-month-performance-evidence`. The working tree was modified
for opt-in instrumentation before the image was built. The tested image ID is
`sha256:870beb552b1991f7b6828e1319abacae0e8f782c52f2c651205436c81164a22e`;
its relevant source/config fingerprint, calculated inside the image with
`tests/collect_verification.py`'s `source_fingerprint()`, is
`1e30ae8b2b78f87e665f926c19762d36c903f3c2033e0fc544f72dd164c6b0a9`.
That fingerprint excludes README/evidence edits and the later SQL timing
utility, which did not participate in the pipeline build.

| Resource | Observed configuration |
|---|---:|
| Host | Windows 10 Pro; Intel Core i5-13400F; 31.82 GiB RAM |
| Docker engine | 29.9.2; 16 CPUs; 15.53 GiB available memory |
| Pipeline container cap | No explicit memory, swap or CPU cap (`docker inspect` reported zero) |
| Runtime | Python 3.11.14; dbt-core 1.10.23; dbt-duckdb 1.10.0; DuckDB 1.4.5; Prefect 2.20.27; Streamlit 1.50.0; PyArrow 21.0.0 |

The container's lack of an explicit cap does not mean unlimited host memory.
The C: drive had about 596.8 GB free before the run.

## Reproducible method

From the repository root, with Docker Desktop running:

```powershell
docker info --format '{{.ServerVersion}} {{.MemTotal}} {{.NCPU}}'
docker compose build pipeline dashboard
python tests/benchmark_pipeline.py --output data/verification/benchmark-2026-11-07
docker compose run --rm pipeline python -m unittest discover -s tests -p "test_*.py"
docker compose run --rm pipeline python tests/verify_warehouse.py
docker compose run --rm pipeline python tests/synthetic_fixture.py
Copy-Item tests/benchmark_dashboard_queries.py data/verification/benchmark-2026-11-07/dashboard_queries_runner.py
docker compose run --rm pipeline python /app/data/verification/benchmark-2026-11-07/dashboard_queries_runner.py --output /app/data/verification/benchmark-2026-11-07/dashboard_queries.json
docker compose up -d dashboard
docker compose exec -T dashboard python -c "import urllib.request; print(urllib.request.urlopen('http://localhost:8501/_stcore/health').read().decode())"
git diff --check
```

The benchmark utility stops the dashboard before candidate publication,
including for Windows file locking. It uses `time.perf_counter()` around the
host Docker command. The Prefect flow uses the same monotonic clock around
major stages and writes timing JSON only when `PIPELINE_METRICS_PATH` is set.
Optional timing writes cannot fail the data build. Image build time, focused
tests, SQL query timings and dashboard restart are outside the pipeline
duration. The dashboard was restarted after validation and returned `ok`.

## Pipeline observations

| Measure | Result |
|---|---:|
| Host `docker compose run` elapsed, including startup/shutdown | 247.206 s |
| Prefect flow elapsed | 232.646 s |
| Source validation and ingestion | 18.594 s |
| Profiling | 3.934 s |
| dbt build and tests | 207.450 s |
| Candidate validation | 2.550 s |
| Publication | 0.111 s |
| Raw files including zone CSV | 408,212,043 bytes (389.3 MiB) |
| Published DuckDB warehouse | 4,534,317,056 bytes (4.223 GiB) |

Within dbt, `summary_metrics_reconciliation` took 125.46 seconds, the
largest single operation in the log. The full measured rebuild still
completed in about four minutes on this machine. No runtime target was
specified, so this observation alone did not justify changing a
reconciliation check or materialization.

The Docker monitor requested a sample every five seconds and obtained 40
samples. Its **observed sampled maximum container usage** was 5,525,475,426
bytes (5.146 GiB). The actual peak between samples may have been higher.
This is Docker container usage, not process RSS; process-level memory was
not measured. The raw samples and actual timestamps are in ignored
`data/verification/benchmark-2026-11-07/host_measurements.json`.

## Reconciliation and checks

| Check | Result |
|---|---:|
| Source rows | 24,083,384 |
| Accepted `fact_trips` rows | 23,886,241 |
| Rejected rows | 197,143 |
| Source = accepted + rejected | Yes |
| Financially eligible rows | 22,560,818 |
| Eligible recorded passenger charges | $637,824,068.09 |
| Daily summary rows | 181 |
| dbt inventory | 12 models and 43 data tests passed; 0 failures/skips |
| Focused Python inventory | 11 passed, including 4 dashboard tests (not 15 unique tests) |
| Synthetic fixture and warehouse signature | Passed |

All requested historical counts match. The synthetic fixture also checked
duplicate-content identity retention and month boundaries. No cleaning,
financial eligibility, reconciliation tolerance or publication rule changed.

## Dashboard timing scope

Browser rendering timings for first load after restart, Manhattan selection,
cross-month selection and reset are **unavailable**. The browser access host
was unavailable, and the open Chrome window could not be attached. A fully
rendered measurement would require all five KPIs, daily charts, heatmap,
pickup charts and payment views to display for the selected filters. The
health response confirms only that Streamlit serves requests.

As a narrower diagnostic, `tests/benchmark_dashboard_queries.py` extracted
the exact `metrics` and `daily_data` SQL templates from `dashboard/app.py`.
Each query used a new read-only DuckDB connection and `fetchdf()`, with three
repetitions per filter case. Times use a monotonic clock; the table gives
medians, while the JSON under ignored `data/verification/benchmark-2026-11-07/`
contains every observation. These are **SQL query timings**, not dashboard or
browser timings. Streamlit cache, Plotly, network transfer and browser paint
are excluded; operating-system/DuckDB cache conditions were not controlled.

| Filter case | KPI SQL median | Daily SQL median | Eligible trips |
|---|---:|---:|---:|
| Full period, all boroughs | 1.0058 s | 0.3469 s | 22,560,818 |
| Full period, Manhattan | 1.0952 s | 0.4827 s | 19,578,020 |
| 15 Mar-15 May, all boroughs | 0.5283 s | 0.2263 s | 7,994,372 |

The `metrics` and `daily_data` totals matched within each filter case. Two
post-run checks first used Windows backslashes in container paths and exited
before running; the same checks passed with `/` paths. The copied SQL timing
utility initially resolved its project root from the copy location; this was
corrected before timings were collected. Neither issue affected the pipeline.

This machine completed the tested six-month workload within its available
Docker memory and disk. The observations do not establish end-to-end dashboard
responsiveness or guarantee performance for several years. Measure a larger
workload before choosing incremental or distributed processing.
