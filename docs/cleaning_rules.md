# NYC Yellow Taxi Data Cleaning Rules

## Purpose

This document defines the initial rules used to transform raw NYC Yellow Taxi trip records into analytics-ready data.

The raw source files will never be modified. Cleaning rules will be applied only when creating staging and analytical models.

## General approach

Records will be classified into three groups:

1. Valid trips suitable for general analysis
2. Valid but special-case trips requiring flags
3. Rejected trips that cannot support reliable analysis

The pipeline will preserve counts of rejected and flagged records so that data-quality decisions remain transparent.

## Date scope

The January 2025 model will include records where:

- Pickup timestamp is on or after 2025-01-01 00:00:00
- Pickup timestamp is before 2025-02-01 00:00:00

Records outside this period are retained in rejected_trips with the
pickup_outside_january_2025 reason.

## Timestamp rules

A trip requires:

- A non-null pickup timestamp
- A non-null drop-off timestamp
- A drop-off timestamp later than the pickup timestamp

Trip duration is calculated as elapsed seconds divided by 60. A trip is
flagged unusually long when elapsed seconds exceed 21,600.

Trips with a duration greater than six hours will be retained in staging but flagged as unusually long. They will be excluded from ordinary trip-duration averages.

## Location rules

A trip requires:

- A non-null pickup location ID
- A non-null drop-off location ID
- Pickup and drop-off location IDs that exist in the official taxi-zone lookup table

The initial profile found no unmatched pickup or drop-off zones.

## Passenger-count rules

Missing passenger counts will not cause a trip to be rejected.

A missing passenger count will remain null and will be identified using a passenger-count-missing flag.

Passenger counts above eight will be retained but flagged as unusual.

Passenger-count analysis will use only non-null and reasonable values.

## Distance rules

Negative trip distances will be rejected.

Zero-distance trips will be retained and flagged. They will be excluded from analyses requiring a meaningful distance, such as fare per mile or average speed.

Trips above 100 miles will be retained in staging but flagged as unusually long. They will be excluded from ordinary distance averages until manually reviewed.

## Financial rules

Negative fare and total amounts may represent refunds, corrections, or reversed transactions.

These records will not be deleted from staging. They will be classified as financial adjustments and excluded from ordinary fare and revenue KPIs.

Standard dashboard and summary metrics use accepted records where:

- Fare amount is greater than or equal to zero
- Total amount is greater than or equal to zero
- Neither amount is missing. Zero amounts remain eligible.

Daily accepted counts include all accepted records, including financial
adjustments and records missing financial amounts. Standard counts and
recorded charges use only eligible records. Recorded charges are
passenger charges, not profit, and cash tips are absent from the source
tip field.
Payment code 0 is labeled "Flex Fare trip".

Each accepted or rejected row represents one physical Parquet source
row. The source filename and file row number form its stable identity.
Identical content gets a duplicate flag, but no row is dropped.

## Derived fields

The transformation will create:

- Pickup date
- Pickup year
- Pickup month
- Pickup day
- Pickup weekday
- Pickup hour
- Weekend indicator
- Trip duration in minutes
- Fare per mile
- Average speed in miles per hour
- Tip percentage
- Financial-adjustment indicator
- Zero-distance indicator
- Missing-passenger-count indicator
- Unusually-long-duration indicator
- Unusually-long-distance indicator

Fare per mile will be calculated only when trip distance is greater than zero.

Average speed will be calculated only when distance and duration are both greater than zero.

Tip percentage will be calculated only when fare amount is greater than zero.

## Rejected-record policy

A record will be rejected from the main analytical fact table when:

- Pickup timestamp is missing
- Drop-off timestamp is missing
- Drop-off is not later than pickup
- Pickup timestamp is outside the selected monthly period
- Pickup location ID is missing
- Drop-off location ID is missing
- Pickup or drop-off location is absent from the official lookup table
- Trip distance is negative

Rejected records will remain available in a separate rejected-record model with a rejection reason.

## Review policy

These rules are initial decisions based on January 2025 profiling results.

They may be refined after inspecting distributions, reviewing official data documentation, and comparing additional months. Any changes will be recorded in this document.

## Missing financial values

Records with missing fare_amount or total_amount remain in the
accepted fact table if they pass the other acceptance checks.
They are flagged with is_financial_data_missing and excluded
from standard dashboard metrics and financial summaries.
Missing amounts are not replaced with zero.
