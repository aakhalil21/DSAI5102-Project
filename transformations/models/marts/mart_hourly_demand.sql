select
    pickup_weekday,
    extract(
        isodow from pickup_datetime
    ) as weekday_number,
    pickup_hour,
    is_weekend,

    count(*)
        as trip_count,

    sum(total_amount)
        as total_revenue,

    avg(fare_amount)
        as average_fare,

    avg(
        case
            when not is_zero_distance
                and not is_unusually_long_distance
            then trip_distance
            else null
        end
    ) as average_trip_distance

from {{ ref('fact_trips') }}

where not is_financial_adjustment

group by
    pickup_weekday,
    weekday_number,
    pickup_hour,
    is_weekend

order by
    weekday_number,
    pickup_hour
