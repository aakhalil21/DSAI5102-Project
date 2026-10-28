# January 2025 Yellow Taxi Data Profile

## Dataset summary

- Total rows: 3,475,226
- Earliest pickup: 2024-12-31 20:47:55
- Latest pickup: 2025-02-01 00:00:44
- Earliest drop-off: 2024-12-18 07:52:40
- Latest drop-off: 2025-02-01 23:44:11
- Distinct pickup location IDs: 261
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
| Missing passenger counts | 540,149 |
| Missing pickup zone IDs | 0 |
| Missing drop-off zone IDs | 0 |
| Drop-off not later than pickup | 2,051 |
| Negative trip distances | 0 |
| Zero trip distances | 90,893 |
| Negative fare amounts | 144,118 |
| Negative total amounts | 63,037 |
| Negative passenger counts | 0 |
| Passenger counts above 8 | 3 |
| Trip distances above 100 miles | 162 |
| Trips lasting more than 6 hours | 1,203 |
| Pickup timestamps outside January 2025 | 22 |
| Pickup zones absent from lookup | 0 |
| Drop-off zones absent from lookup | 0 |

## Initial averages

- Average distance: 5.39 miles
- Average fare: $18.33
- Average total amount: $27.12
- Average duration: 15.06 minutes

## Notes

These results describe the raw source data. The cleaning rules will be selected after reviewing these findings.
