select *
from {{ ref('fact_trips') }}
where
    pickup_datetime
        < timestamp '{{ var("period_start") }} 00:00:00'
    or pickup_datetime
        >= timestamp '{{ var("period_end") }} 00:00:00'
