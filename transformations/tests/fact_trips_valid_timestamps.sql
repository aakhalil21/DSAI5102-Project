select *
from {{ ref('fact_trips') }}
where
    pickup_datetime is null
    or dropoff_datetime is null
    or dropoff_datetime <= pickup_datetime
