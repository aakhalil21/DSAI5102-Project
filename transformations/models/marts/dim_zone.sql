select
    location_id as zone_key,
    borough,
    zone_name,
    service_zone

from {{ ref('stg_taxi_zones') }}
