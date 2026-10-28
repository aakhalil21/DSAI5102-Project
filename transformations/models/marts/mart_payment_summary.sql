with trips as (

    select *
    from {{ ref('fact_trips') }}
    where (not is_financial_adjustment and not is_financial_data_missing)

),

payment_types as (

    select *
    from {{ ref('dim_payment_type') }}

)

select
    trips.payment_type,
    payment_types.payment_type_name,

    count(*)
        as trip_count,

    sum(trips.total_amount)
        as total_revenue,

    avg(trips.fare_amount)
        as average_fare,

    avg(trips.tip_amount)
        as average_tip,

    avg(trips.tip_percentage)
        as average_tip_percentage

from trips

left join payment_types
    on trips.payment_type
    = payment_types.payment_type_key

group by
    trips.payment_type,
    payment_types.payment_type_name

order by trip_count desc
