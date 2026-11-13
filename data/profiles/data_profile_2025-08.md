# August 2025 Yellow Taxi Data Profile

## Dataset summary

- Total rows: 3,574,091
- Earliest pickup: 2009-01-01 12:52:15
- Latest pickup: 2025-09-01 00:00:29
- Earliest drop-off: 2009-01-01 13:12:15
- Latest drop-off: 2025-09-02 08:17:29
- Distinct pickup location IDs: 260
- Distinct drop-off location IDs: 260

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
| Missing passenger counts | 886,234 |
| Missing pickup zone IDs | 0 |
| Missing drop-off zone IDs | 0 |
| Drop-off not later than pickup | 47,833 |
| Negative trip distances | 0 |
| Zero trip distances | 105,184 |
| Negative fare amounts | 261,191 |
| Negative total amounts | 87,940 |
| Negative passenger counts | 0 |
| Passenger counts above 8 | 3 |
| Trip distances above 100 miles | 245 |
| Trips lasting more than 6 hours | 1,028 |
| Pickup timestamps outside August 2025 | 17 |
| Pickup zones absent from lookup | 0 |
| Drop-off zones absent from lookup | 0 |

## Initial averages

- Average distance: 6.86 miles
- Average fare: $20.38
- Average total amount: $29.04
- Average duration: 17.50 minutes

## Notes

These averages describe raw rows with ordered timestamps, non-negative distance, fare, and total amounts. They are not dashboard KPIs: the dashboard applies project-period, location, financial-eligibility, and metric-specific filters to accepted trips.
