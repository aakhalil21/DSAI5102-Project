{#- Incremental: a batch run removes every row it reclassifies (from both
    fact_trips and rejected_trips) before inserting the new classification,
    so a row that moves between the two tables is never duplicated and a
    rerun of the same batch changes nothing. A full rebuild uses
    --full-refresh and simply recreates the table. -#}
{{ config(
    materialized='incremental',
    incremental_strategy='delete+insert',
    unique_key='trip_id',
    on_schema_change='fail',
    pre_hook="{% if is_incremental() %}delete from {{ this }} where trip_id in (select trip_id from {{ ref('int_trip_quality') }}){% endif %}"
) }}

with quality_checked as (

    select *
    from {{ ref('int_trip_quality') }}

),

accepted as (

    select *
    from quality_checked
    where rejection_reason is null

)

select *
from accepted
