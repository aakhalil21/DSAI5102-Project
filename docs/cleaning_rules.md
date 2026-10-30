# NYC Yellow Taxi Data Cleaning Rules

## Purpose

This document defines the rules used to transform raw NYC Yellow Taxi trip records into analytics-ready data.

The pipeline preserves the raw source files unchanged. Cleaning rules apply when creating staging and analytical models.

The raw profiling report averages rows with ordered pickup and drop-off
timestamps and nonnegative distance, fare, and total amounts. Its averages
do not apply the accepted-trip, project-period, known-location, financial
eligibility, and metric-specific filters used by dashboard KPIs, so the
two sets of averages can differ.

## General approach

Records are classified into three groups:

1. Valid trips suitable for general analysis
2. Valid but special-case trips requiring flags
3. Rejected trips that cannot support reliable analysis

The pipeline preserves counts of rejected and flagged records so that data-quality decisions remain transparent.

## Date scope

The January-June 2025 model accepts records where:

- Pickup timestamp is on or after 2025-01-01 00:00:00
- Pickup timestamp is before 2025-07-01 00:00:00

Records outside this period are retained in rejected_trips with the
pickup_outside_project_period reason.

## Timestamp rules

A trip requires:

- A non-null pickup timestamp
- A non-null drop-off timestamp
- A drop-off timestamp later than the pickup timestamp

Trip duration is calculated as elapsed seconds divided by 60. A trip is
flagged unusually long when elapsed seconds exceed 21,600.

Trips with a duration greater than six hours remain in staging and are flagged as unusually long. They are excluded from ordinary trip-duration averages.

## Location rules

A trip requires:

- A non-null pickup location ID
- A non-null drop-off location ID
- Pickup and drop-off location IDs that exist in the official taxi-zone lookup table

The initial profile found no unmatched pickup or drop-off zones.

## Passenger-count rules

A missing passenger count does not cause a trip to be rejected.

A missing passenger count remains null and is identified using a passenger-count-missing flag.

Passenger counts above eight are retained but flagged as unusual.

Passenger-count analysis uses only non-null and reasonable values.

## Distance rules

Negative trip distances are rejected.

Zero-distance trips are retained and flagged. They are excluded from analyses requiring a meaningful distance, such as fare per mile or average speed.

Trips above 100 miles are retained in staging but flagged as unusually long. They are excluded from ordinary distance averages.

## Financial rules

Negative fare and total amounts may represent refunds, corrections, or reversed transactions.

These records remain in staging. They are classified as financial adjustments and excluded from ordinary fare and recorded-charge KPIs.

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
A content fingerprint identifies identical content, but no row is dropped.

## Derived fields

The transformation creates:

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

Fare per mile is calculated only when trip distance is greater than zero and fare is nonnegative.

Average speed is calculated only when distance and duration are both greater than zero.

Tip percentage is calculated only when fare amount is greater than zero and tip amount is nonnegative.

## Rejected-record policy

A record is rejected from the main analytical fact table when:

- Pickup timestamp is missing
- Drop-off timestamp is missing
- Drop-off is not later than pickup
- Pickup timestamp is before 2025-01-01 or on or after 2025-07-01
- Pickup location ID is missing
- Drop-off location ID is missing
- Pickup or drop-off location is absent from the official lookup table
- Trip distance is negative

Rejected records remain available in a separate rejected-record model with a rejection reason. A June 30 pickup ending in July remains in scope because the period rule uses pickup time.

## Review policy

These are the implemented January-June 2025 rules. Changes to them must be recorded here.

## Missing financial values

Records with missing fare_amount or total_amount remain in the
accepted fact table if they pass the other acceptance checks.
They are flagged with is_financial_data_missing and excluded
from standard dashboard metrics and financial summaries.
Missing amounts are not replaced with zero.
