select *
from {{ ref('fact_trips') }}
where
    is_financial_data_missing is distinct from (
        fare_amount is null
        or total_amount is null
    )
    or is_financial_adjustment is distinct from (
        coalesce(fare_amount < 0, false)
        or coalesce(total_amount < 0, false)
    )