with quality_checked as (

    select *
    from {{ ref('int_trip_quality') }}

),

accepted as (

    select *
    from quality_checked
    where rejection_reason is null

)

select *
from accepted
