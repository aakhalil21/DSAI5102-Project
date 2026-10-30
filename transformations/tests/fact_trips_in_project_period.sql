select *
from {{ ref('fact_trips') }}
where
    pickup_datetime
        < timestamp '2025-01-01 00:00:00'
    or pickup_datetime
        >= timestamp '2025-07-01 00:00:00'
