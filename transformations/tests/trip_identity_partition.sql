with source_ids as (
    select trip_id, count(*) as n
    from {{ ref('stg_yellow_taxi_trips') }}
    group by 1
),
output_ids as (
    select trip_id, count(*) as n
    from (
        select trip_id from {{ ref('fact_trips') }}
        union all
        select trip_id from {{ ref('rejected_trips') }}
    )
    group by 1
)
select coalesce(s.trip_id, o.trip_id) as trip_id
from source_ids s
full outer join output_ids o using (trip_id)
where s.n is distinct from o.n
