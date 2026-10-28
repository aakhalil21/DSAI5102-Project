with source_data as (

    select *
    from read_csv_auto(
        '../data/raw/taxi_zone_lookup.csv',
        header = true
    )

),

renamed as (

    select
        cast("LocationID" as integer)
            as location_id,

        trim(cast("Borough" as varchar))
            as borough,

        trim(cast("Zone" as varchar))
            as zone_name,

        trim(cast("service_zone" as varchar))
            as service_zone

    from source_data

)

select *
from renamed
