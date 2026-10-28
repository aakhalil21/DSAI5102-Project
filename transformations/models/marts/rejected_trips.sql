with quality_checked as (

    select *
    from {{ ref('int_trip_quality') }}

),

rejected as (

    select *
    from quality_checked
    where rejection_reason is not null

)

select *
from rejected
