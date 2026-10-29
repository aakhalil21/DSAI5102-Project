with daily_expected as (
    select pickup_date,
        count(*) as accepted_count,
        count(*) filter (where not is_financial_adjustment and not is_financial_data_missing) as standard_count,
        count(*) filter (where is_financial_adjustment) as adjustment_count,
        sum(total_amount) filter (where not is_financial_adjustment and not is_financial_data_missing) as revenue
    from {{ ref('fact_trips') }}
    group by 1
),
daily_errors as (
    select 'daily' as summary, cast(coalesce(e.pickup_date, a.pickup_date) as varchar) as key
    from daily_expected e
    full outer join {{ ref('mart_daily_performance') }} a using (pickup_date)
    where e.accepted_count is distinct from a.accepted_record_count
       or e.standard_count is distinct from a.standard_trip_count
       or e.adjustment_count is distinct from a.financial_adjustment_count
       or abs(coalesce(e.revenue, 0) - coalesce(a.total_revenue, 0)) > 0.01
),
eligible as (
    select * from {{ ref('fact_trips') }}
    where not is_financial_adjustment and not is_financial_data_missing
),
hourly_expected as (
    select extract(isodow from pickup_datetime) as weekday_number, pickup_hour,
        count(*) as trips, sum(total_amount) as revenue
    from eligible group by 1, 2
),
hourly_errors as (
    select 'hourly' as summary, cast(coalesce(e.weekday_number, a.weekday_number) as varchar) || ':' || cast(coalesce(e.pickup_hour, a.pickup_hour) as varchar) as key
    from hourly_expected e
    full outer join {{ ref('mart_hourly_demand') }} a
      on e.weekday_number = a.weekday_number and e.pickup_hour = a.pickup_hour
    where e.trips is distinct from a.trip_count
       or abs(coalesce(e.revenue, 0) - coalesce(a.total_revenue, 0)) > 0.01
),
zone_expected as (
    select pickup_location_id, count(*) as trips, sum(total_amount) as revenue
    from eligible group by 1
),
zone_errors as (
    select 'zone' as summary, cast(coalesce(e.pickup_location_id, a.pickup_location_id) as varchar) as key
    from zone_expected e
    full outer join {{ ref('mart_zone_performance') }} a using (pickup_location_id)
    where e.trips is distinct from a.trip_count
       or abs(coalesce(e.revenue, 0) - coalesce(a.total_revenue, 0)) > 0.01
),
payment_expected as (
    select payment_type, count(*) as trips, sum(total_amount) as revenue
    from eligible group by 1
),
payment_errors as (
    select 'payment' as summary, cast(coalesce(e.payment_type, a.payment_type) as varchar) as key
    from payment_expected e
    full outer join {{ ref('mart_payment_summary') }} a using (payment_type)
    where e.trips is distinct from a.trip_count
       or abs(coalesce(e.revenue, 0) - coalesce(a.total_revenue, 0)) > 0.01
)
select * from daily_errors
union all select * from hourly_errors
union all select * from zone_errors
union all select * from payment_errors
