from pathlib import Path

import duckdb
import pandas as pd
import plotly.express as px
import streamlit as st


PROJECT_ROOT = Path(__file__).resolve().parents[1]

DATABASE_FILE = (
    PROJECT_ROOT
    / "data"
    / "warehouse"
    / "nyc_taxi.duckdb"
)


st.set_page_config(
    page_title="NYC Taxi Analytics",
    page_icon="🚕",
    layout="wide",
)


@st.cache_data(ttl=300)
def run_query(sql, parameters=()):
    """Run a read-only DuckDB query."""

    connection = duckdb.connect(
        str(DATABASE_FILE),
        read_only=True,
    )

    try:
        result = connection.execute(
            sql,
            list(parameters),
        ).fetchdf()
    finally:
        connection.close()

    return result


if not DATABASE_FILE.exists():
    st.error(
        "The analytical warehouse was not found. "
        "Run the data pipeline before starting "
        "the dashboard."
    )
    st.stop()


st.title("NYC Yellow Taxi Analytics")
st.caption(
    "Charts exclude records with missing or negative fare or total amounts. "
    "Recorded charges are passenger charges, not profit, and exclude "
    "cash tips. Tip figures reflect recorded tips; cash tips are "
    "not captured. Average distance excludes zero-distance trips "
    "and trips over 100 miles. Average duration excludes trips "
    "longer than six hours."
)
st.markdown(
    """
    Explore demand, Recorded charges (USD), fares, payment behaviour,
    and pickup-zone performance for January 2025.
    """
)


date_limits = run_query(
    """
    select
        min(pickup_date) as minimum_date,
        max(pickup_date) as maximum_date
    from main.fact_trips
    """
)

minimum_date = date_limits.loc[0, "minimum_date"]
maximum_date = date_limits.loc[0, "maximum_date"]


borough_data = run_query(
    """
    select distinct
        pickup_borough
    from main.fact_trips
    where pickup_borough is not null
    order by pickup_borough
    """
)

borough_options = [
    "All boroughs"
] + borough_data["pickup_borough"].tolist()


st.sidebar.header("Dashboard filters")

selected_dates = st.sidebar.date_input(
    "Pickup date range",
    value=(minimum_date, maximum_date),
    min_value=minimum_date,
    max_value=maximum_date,
)

selected_borough = st.sidebar.selectbox(
    "Pickup borough",
    borough_options,
)

if isinstance(selected_dates, tuple):
    start_date = selected_dates[0]

    if len(selected_dates) == 2:
        end_date = selected_dates[1]
    else:
        end_date = selected_dates[0]
else:
    start_date = selected_dates
    end_date = selected_dates


where_conditions = [
    "pickup_date between ? and ?",
    "(not is_financial_adjustment and not is_financial_data_missing)",
]

query_parameters = [
    start_date,
    end_date,
]

if selected_borough != "All boroughs":
    where_conditions.append(
        "pickup_borough = ?"
    )
    query_parameters.append(selected_borough)

where_clause = " and ".join(where_conditions)


metrics = run_query(
    """
    select
        count(*) as total_trips,
        sum(total_amount) as total_revenue,
        avg(fare_amount) as average_fare,
        avg(
            case
                when not is_zero_distance
                    and not is_unusually_long_distance
                then trip_distance
                else null
            end
        ) as average_distance,
        avg(
            case
                when not is_unusually_long_duration
                then trip_duration_minutes
                else null
            end
        ) as average_duration
    from main.fact_trips
    where {}
    """.format(where_clause),
    tuple(query_parameters),
)


if metrics.loc[0, "total_trips"] == 0:
    st.warning(
        "No trips match the selected filters."
    )
    st.stop()


metric_columns = st.columns(5)

metric_columns[0].metric(
    "Trips with valid financial data",
    "{:,.0f}".format(
        metrics.loc[0, "total_trips"]
    ),
)

metric_columns[1].metric(
    "Recorded charges",
    "${:,.0f}".format(
        metrics.loc[0, "total_revenue"]
    ),
)

metric_columns[2].metric(
    "Average fare",
    "${:,.2f}".format(
        metrics.loc[0, "average_fare"]
    ),
)

metric_columns[3].metric(
    "Average distance",
    "{:,.2f} mi".format(
        metrics.loc[0, "average_distance"]
    ),
)

metric_columns[4].metric(
    "Average duration",
    "{:,.1f} min".format(
        metrics.loc[0, "average_duration"]
    ),
)


st.divider()

daily_data = run_query(
    """
    select
        pickup_date,
        count(*) as trip_count,
        sum(total_amount) as total_revenue
    from main.fact_trips
    where {}
    group by pickup_date
    order by pickup_date
    """.format(where_clause),
    tuple(query_parameters),
)

left_chart, right_chart = st.columns(2)

with left_chart:
    st.subheader("Daily taxi demand")

    daily_trip_figure = px.line(
        daily_data,
        x="pickup_date",
        y="trip_count",
        markers=True,
        labels={
            "pickup_date": "Pickup date",
            "trip_count": "Trips",
        },
    )

    daily_trip_figure.update_layout(
        showlegend=False
    )

    st.plotly_chart(
        daily_trip_figure,
        use_container_width=True,
    )

with right_chart:
    st.subheader("Daily recorded charges")

    daily_revenue_figure = px.line(
        daily_data,
        markers=True,
        x="pickup_date",
        y="total_revenue",
        labels={
            "pickup_date": "Pickup date",
            "total_revenue": "Recorded charges (USD)",
        },
    )

    daily_revenue_figure.update_layout(
        showlegend=False
    )

    st.plotly_chart(
        daily_revenue_figure,
        use_container_width=True,
    )


st.divider()

hourly_data = run_query(
    """
    select
        pickup_weekday,
        extract(
            isodow from pickup_datetime
        ) as weekday_number,
        pickup_hour,
        count(*) as trip_count
    from main.fact_trips
    where {}
    group by
        pickup_weekday,
        weekday_number,
        pickup_hour
    order by
        weekday_number,
        pickup_hour
    """.format(where_clause),
    tuple(query_parameters),
)

weekday_order = [
    "Monday",
    "Tuesday",
    "Wednesday",
    "Thursday",
    "Friday",
    "Saturday",
    "Sunday",
]

hourly_pivot = hourly_data.pivot(
    index="pickup_weekday",
    columns="pickup_hour",
    values="trip_count",
)

hourly_pivot = hourly_pivot.reindex(
    weekday_order
)

hourly_pivot = hourly_pivot.fillna(0)


st.subheader("Demand by weekday and pickup hour")

heatmap = px.imshow(
    hourly_pivot,
    aspect="auto",
    color_continuous_scale="Blues",
    labels={
        "x": "Pickup hour",
        "y": "Weekday",
        "color": "Trips",
    },
)

st.plotly_chart(
    heatmap,
    use_container_width=True,
)


st.divider()

borough_summary = run_query(
    """
    select
        pickup_borough,
        count(*) as trip_count
    from main.fact_trips
    where {}
    group by pickup_borough
    order by trip_count desc
    """.format(where_clause),
    tuple(query_parameters),
)

zone_summary = run_query(
    """
    select
        pickup_zone,
        pickup_borough,
        count(*) as trip_count,
        sum(total_amount) as total_revenue
    from main.fact_trips
    where {}
    group by
        pickup_zone,
        pickup_borough
    order by trip_count desc
    limit 10
    """.format(where_clause),
    tuple(query_parameters),
)

left_chart, right_chart = st.columns(2)

with left_chart:
    st.subheader("Trips by pickup borough")

    borough_figure = px.bar(
        borough_summary,
        x="pickup_borough",
        y="trip_count",
        color="pickup_borough",
        labels={
            "pickup_borough": "Pickup borough",
            "trip_count": "Trips",
        },
    )

    borough_figure.update_layout(
        showlegend=False
    )

    st.plotly_chart(
        borough_figure,
        use_container_width=True,
    )

with right_chart:
    st.subheader("Top 10 pickup zones")

    zone_figure = px.bar(
        zone_summary.sort_values(
            "trip_count"
        ),
        x="trip_count",
        y="pickup_zone",
        orientation="h",
        color="pickup_borough",
        labels={
            "pickup_zone": "Pickup zone",
            "trip_count": "Trips",
            "pickup_borough": "Borough",
        },
    )

    st.plotly_chart(
        zone_figure,
        use_container_width=True,
    )


st.divider()

payment_summary = run_query(
    """
    select
        payments.payment_type_name,
        count(*) as trip_count,
        sum(trips.total_amount) as total_revenue,
        avg(trips.tip_percentage)
            as average_tip_percentage
    from main.fact_trips as trips

    left join main.dim_payment_type as payments
        on trips.payment_type
        = payments.payment_type_key

    where {}
    group by payments.payment_type_name
    order by trip_count desc
    """.format(
        where_clause.replace(
            "pickup_date",
            "trips.pickup_date",
        ).replace(
            "is_financial_adjustment",
            "trips.is_financial_adjustment",
        ).replace(
            "pickup_borough",
            "trips.pickup_borough",
        ).replace(
            "is_financial_data_missing",
            "trips.is_financial_data_missing",
        )
            ),
    tuple(query_parameters),
)

left_chart, right_chart = st.columns(2)

with left_chart:
    st.subheader("Payment methods")

    payment_figure = px.pie(
        payment_summary,
        names="payment_type_name",
        values="trip_count",
        hole=0.45,
    )

    st.plotly_chart(
        payment_figure,
        use_container_width=True,
    )

with right_chart:
    st.subheader("Payment summary")

    display_payment_data = payment_summary.copy()

    display_payment_data.columns = [
        "Payment method",
        "Trips",
        "Recorded charges (USD)",
        "Average tip percentage",
    ]

    st.dataframe(
        display_payment_data,
        use_container_width=True,
        hide_index=True,
    )


st.divider()

st.caption(
    "Source: New York City Taxi and Limousine "
    "Commission Yellow Taxi Trip Records."
)
