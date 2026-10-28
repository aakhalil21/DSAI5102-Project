with payment_codes as (

    select distinct
        payment_type
    from {{ ref('fact_trips') }}

),

payment_labels as (

    select
        payment_type
            as payment_type_key,

        case payment_type
            when 0 then 'Flex Fare trip'
            when 1 then 'Credit card'
            when 2 then 'Cash'
            when 3 then 'No charge'
            when 4 then 'Dispute'
            when 5 then 'Unknown'
            when 6 then 'Voided trip'
            else 'Not specified'
        end as payment_type_name

    from payment_codes

)

select *
from payment_labels
