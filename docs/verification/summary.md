# Final verification evidence

Generated UTC: 2026-10-30T13:59:30Z
Branch: `fix/final-verification`
Starting commit: `ce9d05adfd944468a38a4658fc07dc40fcae892d`
Starting tree clean: True
Modified-tree source fingerprint (SHA-256): `8b0622a0a95498104054611355adc7a762afd81431ef4d64bfad7a463fec79e3`

| Month | Source | Accepted | Rejected | Reconciles |
|---|---:|---:|---:|---|
| 2025-01 | 3,475,226 | 3,473,154 | 2,072 | Yes |
| 2025-02 | 3,577,543 | 3,572,379 | 5,164 | Yes |
| 2025-03 | 4,145,257 | 4,122,975 | 22,282 | Yes |
| 2025-04 | 3,970,553 | 3,935,784 | 34,769 | Yes |
| 2025-05 | 4,591,845 | 4,527,572 | 64,273 | Yes |
| 2025-06 | 4,322,960 | 4,254,377 | 68,583 | Yes |
| **Total** | **24,083,384** | **23,886,241** | **197,143** | **Yes** |

## Checks

- dbt: 12 model builds and 43 data tests passed; no dbt failures or skips.
- Warehouse: 22,560,818 eligible rows, $637,824,068.09 recorded charges; 181 daily rows from 2025-01-01 through 2025-06-30; no duplicate trip IDs.
- Source URLs, byte sizes, SHA-256 hashes, runtime versions, and dbt generation timestamp are in `details.json`.
- Full pipeline log and raw dbt artifacts are retained under ignored `data/verification/`.
- Focused Python, synthetic fixture, warehouse verification, dashboard health, and browser results are recorded separately when run.

## Later dashboard-only browser review

The full-pipeline fingerprint above applies to the image used for the
January–June build. A later presentation-only heatmap tick-spacing change
was built and tested in a dashboard-only image with source fingerprint
`c80ed6715d92919c3e6d3b6cfcd551c75c127b9e51351f85707fd83928b7f6b4`.
Four dashboard tests passed, the restarted health endpoint returned `ok`,
and desktop and 400 px browser checks are recorded in `browser_review.md`.
Screenshots and full browser comparison output are under ignored
`data/verification/`.
