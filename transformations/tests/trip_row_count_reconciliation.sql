with counts as (
    select
        (select count(*)
         from {{ ref('stg_yellow_taxi_trips') }}) as source_rows,

        (select count(*)
         from {{ ref('fact_trips') }}) as accepted_rows,

        (select count(*)
         from {{ ref('rejected_trips') }}) as rejected_rows
)

select *
from counts
where source_rows != accepted_rows + rejected_rows