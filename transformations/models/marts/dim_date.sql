with dates as (

    select distinct
        pickup_date
    from {{ ref('fact_trips') }}
    where pickup_date is not null

),

date_attributes as (

    select
        pickup_date
            as date_key,

        extract(
            year from pickup_date
        ) as year_number,

        extract(
            month from pickup_date
        ) as month_number,

        monthname(pickup_date)
            as month_name,

        extract(
            day from pickup_date
        ) as day_number,

        extract(
            isodow from pickup_date
        ) as weekday_number,

        dayname(pickup_date)
            as weekday_name,

        case
            when extract(
                isodow from pickup_date
            ) in (6, 7)
            then true
            else false
        end as is_weekend

    from dates

)

select *
from date_attributes
order by date_key
