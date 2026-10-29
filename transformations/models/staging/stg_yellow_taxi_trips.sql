with source_data as (

    select *,
        'yellow_tripdata_2025-01.parquet' as source_filename,
        file_row_number as source_row_number,
    from read_parquet(
        '{{ env_var("DBT_TRIP_SOURCE", "../data/raw/yellow_tripdata_2025-01.parquet") }}',
        file_row_number = true
    ) as source_data

),

renamed as (

    select
        source_filename,
        source_row_number,
        md5(source_filename || ':' || cast(source_row_number as varchar))
            as trip_id,
        md5(to_json(struct_pack(
            VendorID := VendorID,
            tpep_pickup_datetime := tpep_pickup_datetime,
            tpep_dropoff_datetime := tpep_dropoff_datetime,
            passenger_count := passenger_count,
            trip_distance := trip_distance,
            RatecodeID := RatecodeID,
            store_and_fwd_flag := store_and_fwd_flag,
            PULocationID := PULocationID,
            DOLocationID := DOLocationID,
            payment_type := payment_type,
            fare_amount := fare_amount,
            extra := extra,
            mta_tax := mta_tax,
            tip_amount := tip_amount,
            tolls_amount := tolls_amount,
            improvement_surcharge := improvement_surcharge,
            total_amount := total_amount,
            congestion_surcharge := congestion_surcharge,
            Airport_fee := Airport_fee,
            cbd_congestion_fee := cbd_congestion_fee
        ))) as content_fingerprint,
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
