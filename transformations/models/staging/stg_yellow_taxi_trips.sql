with source_data as (

    select *
    from read_parquet(
        '../data/raw/yellow_tripdata_2025-01.parquet'
    )

),

renamed as (

    select
        cast(VendorID as integer)
            as vendor_id,

        cast(tpep_pickup_datetime as timestamp)
            as pickup_datetime,

        cast(tpep_dropoff_datetime as timestamp)
            as dropoff_datetime,

        cast(passenger_count as integer)
            as passenger_count,

        cast(trip_distance as double)
            as trip_distance,

        cast(RatecodeID as integer)
            as rate_code_id,

        cast(store_and_fwd_flag as varchar)
            as store_and_forward_flag,

        cast(PULocationID as integer)
            as pickup_location_id,

        cast(DOLocationID as integer)
            as dropoff_location_id,

        cast(payment_type as integer)
            as payment_type,

        cast(fare_amount as double)
            as fare_amount,

        cast(extra as double)
            as extra_amount,

        cast(mta_tax as double)
            as mta_tax,

        cast(tip_amount as double)
            as tip_amount,

        cast(tolls_amount as double)
            as tolls_amount,

        cast(improvement_surcharge as double)
            as improvement_surcharge,

        cast(total_amount as double)
            as total_amount,

        cast(congestion_surcharge as double)
            as congestion_surcharge,

        cast(Airport_fee as double)
            as airport_fee,

        cast(cbd_congestion_fee as double)
            as cbd_congestion_fee

    from source_data

)

select *
from renamed
