with trips as (

    select *
    from {{ ref('stg_yellow_taxi_trips') }}

),

pickup_zones as (

    select *
    from {{ ref('stg_taxi_zones') }}

),

dropoff_zones as (

    select *
    from {{ ref('stg_taxi_zones') }}

),

enriched as (

    select
        trips.*,
        count(*) over (partition by trips.content_fingerprint) > 1
            as is_duplicate_content,

        pickup_zones.borough
            as pickup_borough,

        pickup_zones.zone_name
            as pickup_zone,

        pickup_zones.service_zone
            as pickup_service_zone,

        dropoff_zones.borough
            as dropoff_borough,

        dropoff_zones.zone_name
            as dropoff_zone,

        dropoff_zones.service_zone
            as dropoff_service_zone,

        date_diff(
            'second',
            trips.pickup_datetime,
            trips.dropoff_datetime
        ) / 60.0 as trip_duration_minutes,

        cast(trips.pickup_datetime as date)
            as pickup_date,

        extract(
            year from trips.pickup_datetime
        ) as pickup_year,

        extract(
            month from trips.pickup_datetime
        ) as pickup_month,

        extract(
            day from trips.pickup_datetime
        ) as pickup_day,

        extract(
            hour from trips.pickup_datetime
        ) as pickup_hour,

        dayname(trips.pickup_datetime)
            as pickup_weekday,

        case
            when extract(
                isodow from trips.pickup_datetime
            ) in (6, 7)
            then true
            else false
        end as is_weekend,

        case
            when trips.passenger_count is null
            then true
            else false
        end as is_passenger_count_missing,

        case
            when trips.trip_distance = 0
            then true
            else false
        end as is_zero_distance,

        case
            when trips.trip_distance > 100
            then true
            else false
        end as is_unusually_long_distance,

        case
            when date_diff(
                'second',
                trips.pickup_datetime,
                trips.dropoff_datetime
            ) > 21600
            then true
            else false
        end as is_unusually_long_duration,

        case
            when trips.passenger_count > 8
            then true
            else false
        end as is_unusually_high_passenger_count,

        case
            when trips.fare_amount < 0
                or trips.total_amount < 0
            then true
            else false
        end as is_financial_adjustment,
        case
            when trips.fare_amount is null
                or trips.total_amount is null
            then true
            else false
        end as is_financial_data_missing,
        case
            when trips.trip_distance > 0
                and trips.fare_amount >= 0
            then
                trips.fare_amount
                / trips.trip_distance
            else null
        end as fare_per_mile,

        case
            when trips.trip_distance > 0
                and date_diff(
                    'second',
                    trips.pickup_datetime,
                    trips.dropoff_datetime
                ) > 0
            then
                trips.trip_distance
                / (
                    date_diff(
                        'second',
                        trips.pickup_datetime,
                        trips.dropoff_datetime
                    ) / 3600.0
                )
            else null
        end as average_speed_mph,

        case
            when trips.fare_amount > 0
                and trips.tip_amount >= 0
            then
                (
                    trips.tip_amount
                    / trips.fare_amount
                ) * 100
            else null
        end as tip_percentage,

        case
            when trips.pickup_datetime is null
                then 'missing_pickup_timestamp'

            when trips.dropoff_datetime is null
                then 'missing_dropoff_timestamp'

            when trips.dropoff_datetime
                <= trips.pickup_datetime
                then 'invalid_timestamp_order'

            when trips.pickup_datetime
                < timestamp '2025-01-01 00:00:00'
                or trips.pickup_datetime
                >= timestamp '2025-02-01 00:00:00'
                then 'pickup_outside_january_2025'

            when trips.pickup_location_id is null
                then 'missing_pickup_location'

            when trips.dropoff_location_id is null
                then 'missing_dropoff_location'

            when pickup_zones.location_id is null
                then 'unknown_pickup_location'

            when dropoff_zones.location_id is null
                then 'unknown_dropoff_location'

            when trips.trip_distance < 0
                then 'negative_trip_distance'

            else null
        end as rejection_reason

    from trips

    left join pickup_zones
        on trips.pickup_location_id
        = pickup_zones.location_id

    left join dropoff_zones
        on trips.dropoff_location_id
        = dropoff_zones.location_id

)

select *
from enriched
