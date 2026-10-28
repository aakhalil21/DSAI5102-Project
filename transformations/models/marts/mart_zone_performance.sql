select
    pickup_location_id,
    pickup_borough,
    pickup_zone,
    pickup_service_zone,

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
    ) as average_trip_distance,

    avg(
        case
            when not is_unusually_long_duration
            then trip_duration_minutes
            else null
        end
    ) as average_trip_duration_minutes,

    sum(tip_amount)
        as total_tip_amount,

    avg(tip_percentage)
        as average_tip_percentage

from {{ ref('fact_trips') }}

where not is_financial_adjustment

group by
    pickup_location_id,
    pickup_borough,
    pickup_zone,
    pickup_service_zone

order by trip_count desc
