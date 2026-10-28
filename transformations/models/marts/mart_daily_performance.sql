select
    pickup_date,

    count(*)
        as accepted_record_count,

    count_if(
        (not is_financial_adjustment and not is_financial_data_missing)
    ) as standard_trip_count,

    count_if(
        is_financial_adjustment
    ) as financial_adjustment_count,

    count_if(
        is_zero_distance
    ) as zero_distance_count,

    count_if(
        is_passenger_count_missing
    ) as missing_passenger_count,

    sum(
        case
            when (not is_financial_adjustment and not is_financial_data_missing)
            then total_amount
            else 0
        end
    ) as total_revenue,

    avg(
        case
            when (not is_financial_adjustment and not is_financial_data_missing)
                and not is_zero_distance
                and not is_unusually_long_distance
            then trip_distance
            else null
        end
    ) as average_trip_distance,

    avg(
        case
            when (not is_financial_adjustment and not is_financial_data_missing)
                and not is_unusually_long_duration
            then trip_duration_minutes
            else null
        end
    ) as average_trip_duration_minutes,

    avg(
        case
            when (not is_financial_adjustment and not is_financial_data_missing)
            then fare_amount
            else null
        end
    ) as average_fare

from {{ ref('fact_trips') }}

group by pickup_date
order by pickup_date
