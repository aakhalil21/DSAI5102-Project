# Dashboard browser review

Reviewed in Google Chrome on 2026-10-30 UTC, on `fix/final-verification`.
The review used the published January–June warehouse without rerunning the
pipeline or downloading data. The original full-pipeline build is documented
in `summary.md` and `details.json` with source fingerprint
`8b0622a0a95498104054611355adc7a762afd81431ef4d64bfad7a463fec79e3`.

## Dashboard-only correction and evidence scope

At a responsive viewport of 400 × 888 CSS pixels, the heatmap's two-hour
x-axis ticks were crowded and rotated. I changed only the heatmap tick
spacing from two hours to four in `dashboard/app.py`; all 24 hour cells,
data, calculations, and metric definitions remain unchanged. I rebuilt and
restarted only the dashboard service. Four dashboard tests passed in the
updated dashboard image (`data/verification/dashboard-only-tests.log`), and
the restarted dashboard health endpoint returned `ok`
(`data/verification/dashboard-health.log`).

The updated dashboard image has source fingerprint
`c80ed6715d92919c3e6d3b6cfcd551c75c127b9e51351f85707fd83928b7f6b4`.
The updated `dashboard/app.py` SHA-256 is
`ee36aa74fa0d51f5d0761f12169ba42c49deefd4c56ad9e388ed65fb9728e9a6`.
The earlier dbt and full-pipeline results apply to the earlier source
fingerprint; the dashboard-only tests and browser checks apply to the
updated dashboard image.

## Live browser checks

| Check | Observed result |
|---|---|
| Initial load and reset | January 1–June 30, 2025; All boroughs; 22,560,818 eligible trips and $637.82M displayed. KPI help shows exact charges of $637,824,068.09. Reset restored the full range, KPIs, charts, and payment table. |
| Cross-month range | January 28–February 3 showed 832,546 eligible trips and $21.88M. The warehouse query returned $21,883,673.04 before display rounding. Daily charts and heatmap updated. |
| Single day | January 28–28 showed 109,782 trips and $2.89M; the one-day charts displayed a point. |
| Manhattan on that day | 99,253 trips, $2.28M, $14.61 average fare, 2.20 mi average distance, and 13.1 min average duration. Borough and zone charts and payment rows updated. The five payment rows sum to 99,253 trips. |
| Manhattan across January 28–February 3 on the updated image | 745,670 trips and $17.02M, matching the read-only warehouse query ($17,022,562.82 before rounding). Daily charts and the payment table updated. Reset then returned to the complete range and all boroughs. |
| Heatmap | Seven weekdays remain visible. The source reindexes hours 0–23; a live browser hover on the last column displayed Wednesday 23:00 and 121,854 trips. Four-hour tick labels are readable at 400 px. |
| Top zones | Full-period ranking starts with Upper East Side South. Its hover shows location ID #237 and 1,019,855 trips, matching the warehouse query. Colours and borough legend remain consistent. |
| Controls | Calendar and borough dropdown opened normally at desktop and 400 px. The date picker selected a cross-month range and a same-day range. The focused controls had visible outlines. KPI help and chart hover details were readable. |
| Desktop layout | At about 1380 px window width, header corners, KPI labels and values, charts, section headings, legend, and all payment-table columns were visible without overlap. |
| Narrow layout | At 400 px responsive width, header, badges, KPI cards, charts, and legend fit. Chrome reported `clientWidth=400`, `documentElement.scrollWidth=400`, and `body.scrollWidth=400`: no page-wide horizontal overflow. The payment table scrolls internally to reveal Charges and Avg. tip (%); its swipe instruction is shown at this width. |

The independent read-only comparison query is saved at
`data/verification/browser_expected.py`; its output is
`data/verification/browser_expected.json`. It confirms the displayed KPI
values and that daily and payment trip counts reconcile for the compared
filters.

## Screenshots

Screenshots are local and ignored by Git. Share the directory
`data/verification/screenshots/` with a teammate when sharing the review.

| View | File |
|---|---|
| Full-period desktop overview after correction | `desktop-full-overview-after.png` |
| Cross-month desktop filter on updated image | `desktop-cross-month-after.png` |
| Manhattan filter on updated image | `desktop-manhattan-cross-month-after.png` |
| Manhattan single day and payment detail before tick correction | `desktop-manhattan-single-day.png`, `desktop-manhattan-payment.png` |
| 400 px overview and final heatmap after correction | `narrow-400-overview-after.png`, `narrow-400-heatmap-after.png` |
| 400 px payment table and tooltip | `narrow-400-payment-table.png`, `narrow-400-exact-charge-tooltip.png` |
| 400 px location ID and 23:00 hover | `narrow-400-zone-hover.png`, `narrow-400-hour-23-hover.png` |
| 400 px dropdown | `narrow-400-borough-dropdown.png` |

## Limits and warnings

- Every available day/borough pair in the published data has at least one
  eligible trip, so a live no-eligible selection was unavailable. The saved
  11-test Python run includes dedicated empty-warehouse and no-eligible
  AppTest cases. Those automated cases do not replace a live browser view.
- The 400 px review used Chrome responsive emulation, not a physical phone.
  Focus outlines were visible; a complete keyboard-only traversal and
  touch-gesture audit were not performed.
- Chrome DevTools showed a nonfatal Popper `preventOverflow`/`hide` modifier
  warning while opening controls. No visible control failure resulted.
  The pipeline and Python warnings remain in their saved logs.

No other reproducible visual or interactive defect was found in the
reviewed states.
