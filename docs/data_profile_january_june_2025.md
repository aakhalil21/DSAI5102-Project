# January-June 2025 Yellow Taxi Data Profile

## Dataset summary

- Total rows: 24,083,384
- Earliest pickup: 2007-12-05 18:45:00
- Latest pickup: 2025-06-30 23:59:59
- Earliest drop-off: 2007-12-05 19:02:00
- Latest drop-off: 2025-07-01 22:36:42
- Distinct pickup location IDs: 262
- Distinct drop-off location IDs: 263

## Schema

| Column | Data type | Nullable |
|---|---|---|
| VendorID | INTEGER | YES |
| tpep_pickup_datetime | TIMESTAMP | YES |
| tpep_dropoff_datetime | TIMESTAMP | YES |
| passenger_count | BIGINT | YES |
| trip_distance | DOUBLE | YES |
| RatecodeID | BIGINT | YES |
| store_and_fwd_flag | VARCHAR | YES |
| PULocationID | INTEGER | YES |
| DOLocationID | INTEGER | YES |
| payment_type | BIGINT | YES |
| fare_amount | DOUBLE | YES |
| extra | DOUBLE | YES |
| mta_tax | DOUBLE | YES |
| tip_amount | DOUBLE | YES |
| tolls_amount | DOUBLE | YES |
| improvement_surcharge | DOUBLE | YES |
| total_amount | DOUBLE | YES |
| congestion_surcharge | DOUBLE | YES |
| Airport_fee | DOUBLE | YES |
| cbd_congestion_fee | DOUBLE | YES |

## Data-quality findings

| Check | Affected rows |
|---|---:|
| Missing pickup timestamps | 0 |
| Missing drop-off timestamps | 0 |
| Missing passenger counts | 5,418,601 |
| Missing pickup zone IDs | 0 |
| Missing drop-off zone IDs | 0 |
| Drop-off not later than pickup | 197,119 |
| Negative trip distances | 0 |
| Zero trip distances | 661,842 |
| Negative fare amounts | 1,323,048 |
| Negative total amounts | 446,311 |
| Negative passenger counts | 0 |
| Passenger counts above 8 | 16 |
| Trip distances above 100 miles | 1,488 |
| Trips lasting more than 6 hours | 7,581 |
| Pickup timestamps outside January-June 2025 | 24 |
| Pickup zones absent from lookup | 0 |
| Drop-off zones absent from lookup | 0 |

## Initial averages

- Average distance: 6.36 miles
- Average fare: $19.54
- Average total amount: $28.27
- Average duration: 16.62 minutes

## Notes

These averages describe raw rows with ordered timestamps, non-negative distance, fare, and total amounts. They are not dashboard KPIs: the dashboard applies project-period, location, financial-eligibility, and metric-specific filters to accepted trips.
