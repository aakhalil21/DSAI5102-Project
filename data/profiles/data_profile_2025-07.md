# July 2025 Yellow Taxi Data Profile

## Dataset summary

- Total rows: 3,898,963
- Earliest pickup: 2009-01-01 08:52:26
- Latest pickup: 2025-07-31 23:59:59
- Earliest drop-off: 2009-01-01 10:00:26
- Latest drop-off: 2025-08-03 17:03:02
- Distinct pickup location IDs: 261
- Distinct drop-off location IDs: 261

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
| Missing passenger counts | 1,038,755 |
| Missing pickup zone IDs | 0 |
| Missing drop-off zone IDs | 0 |
| Drop-off not later than pickup | 56,064 |
| Negative trip distances | 0 |
| Zero trip distances | 123,774 |
| Negative fare amounts | 247,088 |
| Negative total amounts | 76,455 |
| Negative passenger counts | 0 |
| Passenger counts above 8 | 10 |
| Trip distances above 100 miles | 274 |
| Trips lasting more than 6 hours | 934 |
| Pickup timestamps outside July 2025 | 7 |
| Pickup zones absent from lookup | 0 |
| Drop-off zones absent from lookup | 0 |

## Initial averages

- Average distance: 6.82 miles
- Average fare: $20.59
- Average total amount: $29.13
- Average duration: 17.33 minutes

## Notes

These averages describe raw rows with ordered timestamps, non-negative distance, fare, and total amounts. They are not dashboard KPIs: the dashboard applies project-period, location, financial-eligibility, and metric-specific filters to accepted trips.
