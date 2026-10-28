select *
from {{ ref('fact_trips') }}
where rejection_reason is not null
