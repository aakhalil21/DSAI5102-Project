# Verification package

`summary.md` and `details.json` are generated from the published warehouse,
the raw source manifest, and the persisted dbt `run_results.json`. The
starting Git commit identifies the pre-change baseline. The source
fingerprint identifies the modified source tree tested in Docker; it does
not claim that the unchanged starting commit produced these results.

The generated files under `data/verification/` stay local and are ignored
by Git. They include the full pipeline log, dbt `target` and `logs`, and
captured output from the focused Python tests, synthetic fixture, warehouse
verification, and dashboard health check. Share them with the small summary
when an independent reviewer needs the complete logs.

`browser_review.md` records the later desktop and 400 px browser checks,
the dashboard-only correction, its separate source fingerprint, and the
locations of screenshots under `data/verification/screenshots/`.

Commands for the final run (PowerShell from the repository root):

```powershell
docker compose build pipeline dashboard
docker compose run --rm pipeline python tests/synthetic_fixture.py
docker compose stop dashboard
docker compose run --rm pipeline
docker compose run --rm pipeline python -m unittest discover -s tests -p 'test_*.py'
docker compose run --rm pipeline python tests/verify_warehouse.py
docker compose run --rm pipeline python tests/collect_verification.py --starting-commit ce9d05adfd944468a38a4658fc07dc40fcae892d --branch fix/final-verification --started-clean
docker compose up -d dashboard
docker compose exec -T dashboard python -c "import urllib.request; print(urllib.request.urlopen('http://localhost:8501/_stcore/health').read().decode())"
```

The actual command outputs and warnings are captured in the run's local
logs. A successful health response establishes that Streamlit is serving;
it does not establish that every chart or interaction works.
