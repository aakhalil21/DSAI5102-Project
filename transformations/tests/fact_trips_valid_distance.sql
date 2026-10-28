select *
from {{ ref('fact_trips') }}
where trip_distance < 0
