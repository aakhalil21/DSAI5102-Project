import html
import os
from pathlib import Path

import duckdb
import pandas as pd
import plotly.express as px
import streamlit as st


PROJECT_ROOT = Path(__file__).resolve().parents[1]

DATABASE_FILE = Path(os.getenv(
    "DASHBOARD_WAREHOUSE_PATH",
    str(PROJECT_ROOT / "data" / "warehouse" / "nyc_taxi.duckdb"),
))


st.set_page_config(
    page_title="NYC Taxi Analytics",
    page_icon="🚕",
    layout="wide",
)

BLUE = "#356AE6"
TEAL = "#168B86"
VIOLET = "#8070BE"
AMBER = "#C99532"
SLATE = "#8492A6"
NAVY = "#142438"
INK = "#1C2B3A"
MUTED = "#536579"
GRID = "#E5ECF2"

BOROUGH_COLORS = {
    "Manhattan": BLUE,
    "Queens": TEAL,
    "Brooklyn": VIOLET,
    "Bronx": AMBER,
    "Staten Island": "#6E7DA9",
    "EWR": "#6A8093",
    "Unknown": SLATE,
    "N/A": "#A8B3C0",
}
PAYMENT_COLORS = {
    "Credit card": BLUE,
    "Cash": TEAL,
    "Flex Fare trip": VIOLET,
    "Dispute": AMBER,
    "No charge": SLATE,
    "Unknown": "#ADB8C5",
    "Not specified": "#ADB8C5",
}
PLOT_CONFIG = {"displayModeBar": "hover", "displaylogo": False}

st.markdown(
    """
    <style>
    .block-container {padding-top: 3.5rem; padding-bottom: 2.5rem; max-width: 1380px;}
    .taxi-header {
        background: #142438;
        color: #F8FAFC;
        border: 1px solid #293E55;
        border-radius: 18px;
        padding: 1.5rem 1.75rem;
        box-shadow: 0 8px 24px rgba(20, 36, 56, 0.11);
    }
    .taxi-header .eyebrow {
        color: #E5C176;
        font-size: 0.72rem;
        font-weight: 700;
        letter-spacing: 0.14em;
        text-transform: uppercase;
        margin: 0 0 0.5rem;
    }
    .taxi-header h1 {
        color: #FFFFFF;
        font-size: clamp(2.125rem, 3vw, 2.5rem);
        font-weight: 680;
        letter-spacing: -0.035em;
        line-height: 1.15;
        margin: 0 0 0.5rem;
        padding: 0;
    }
    .taxi-header .subtitle {color: #D9E5EF; margin: 0 0 1rem; line-height: 1.45;}
    .taxi-header .scope-badges {display: flex; flex-wrap: wrap; gap: 0.5rem;}
    .taxi-header .scope-badge {
        color: #F7FAFC;
        background: #263C54;
        border: 1px solid #40566D;
        border-radius: 7px;
        display: inline-block;
        font-size: 0.8rem;
        font-weight: 600;
        padding: 0.3rem 0.65rem;
    }
    .metric-note {color: #536579; margin: 0 0 0.3rem; padding-top: 1.1rem;}
    .block-container h3 {
        border-left: 0;
        letter-spacing: -0.02em;
        padding-left: 0.75rem;
        position: relative;
    }
    .block-container h3::before {
        background: #C99532;
        border-radius: 2px;
        content: "";
        height: 1.05em;
        left: 0;
        position: absolute;
        top: 50%;
        transform: translateY(-50%);
        width: 3px;
    }
    div[data-testid="stSidebar"] [data-testid="stSidebarContent"] {color: #F2F6FA;}
    div[data-testid="stSidebar"] [data-testid="stCaptionContainer"] {color: #D5E0EA;}
    div[data-testid="stSidebar"] button,
    div[data-testid="stSidebar"] input,
    div[data-testid="stSidebar"] [data-baseweb="select"] > div {
        transition: border-color 180ms ease, background-color 180ms ease,
                    box-shadow 180ms ease;
    }
    div[data-testid="stSidebar"] button:hover,
    div[data-testid="stSidebar"] input:hover,
    div[data-testid="stSidebar"] [data-baseweb="select"] > div:hover {
        border-color: #91B2E9;
        background-color: #30465E;
    }
    div[data-testid="stSidebar"] button:focus-visible,
    div[data-testid="stSidebar"] input:focus-visible,
    div[data-testid="stSidebar"] [data-baseweb="select"]:focus-within {
        outline: 2px solid #E5C176;
        outline-offset: 2px;
    }
    div[data-testid="stMetric"] {
        background: #E7EFFE;
        border: 1px solid #C8D9F7;
        border-top: 3px solid #356AE6;
        border-radius: 14px;
        padding: 1rem 0.95rem;
        min-height: 138px;
        position: relative;
        box-shadow: 0 4px 14px rgba(30, 51, 74, 0.06);
    }
    .st-key-kpi-charges div[data-testid="stMetric"],
    .st-key-kpi-fare div[data-testid="stMetric"] {
        background: #E4F3F0;
        border-color: #C3E2DC;
        border-top-color: #168B86;
    }
    .st-key-kpi-distance div[data-testid="stMetric"],
    .st-key-kpi-duration div[data-testid="stMetric"] {
        background: #EEEAF8;
        border-color: #D9D1EF;
        border-top-color: #8070BE;
    }
    div[data-testid="stMetric"]::after {
        border: 1px solid currentColor;
        border-radius: 8px;
        color: #356AE6;
        content: "↗";
        display: grid;
        font-size: 0.95rem;
        font-weight: 600;
        height: 1.7rem;
        place-items: center;
        position: absolute;
        right: 0.85rem;
        top: 0.8rem;
        width: 1.7rem;
    }
    .st-key-kpi-charges div[data-testid="stMetric"]::after {content: "$"; color: #168B86;}
    .st-key-kpi-fare div[data-testid="stMetric"]::after {content: "◇"; color: #168B86;}
    .st-key-kpi-distance div[data-testid="stMetric"]::after {content: "↔"; color: #8070BE;}
    .st-key-kpi-duration div[data-testid="stMetric"]::after {content: "◷"; color: #8070BE;}
    div[data-testid="stMetricLabel"] {padding-right: 2.15rem;}
    div[data-testid="stMetricValue"] {
        color: #172A3B;
        font-size: clamp(1.55rem, 2vw, 2.15rem);
        font-variant-numeric: tabular-nums;
        letter-spacing: -0.04em;
    }
    div[data-testid="stPlotlyChart"] {
        background: #FFFFFF;
        border: 1px solid #D7E0E9;
        border-radius: 14px;
        box-shadow: 0 5px 18px rgba(30, 51, 74, 0.055);
        overflow: hidden;
        padding: 0;
    }
    div[data-testid="stDataFrame"] {
        background: #FFFFFF;
        border: 1px solid #D7E0E9;
        border-radius: 14px;
        box-shadow: 0 5px 18px rgba(30, 51, 74, 0.055);
        overflow: hidden;
    }
    .zone-legend {display: flex; flex-wrap: wrap; gap: 0.35rem 0.9rem; color: #536579; font-size: 0.78rem;}
    .zone-legend span {display: inline-flex; align-items: center; gap: 0.35rem;}
    .zone-legend i {display: inline-block; width: 0.6rem; height: 0.6rem; border-radius: 2px;}
    .table-scroll-hint {display: none;}
    @media (max-width: 1600px) {
        div[data-testid="stMetric"]::after {display: none;}
        div[data-testid="stMetricLabel"] {padding-right: 0;}
    }
    @media (max-width: 900px) {
        .block-container {padding: 3.5rem 1rem 2rem;}
        .taxi-header {padding: 1.5rem;}
        .taxi-header h1 {font-size: 1.9rem;}
        div[data-testid="stMetric"] {min-height: 116px;}
        .st-key-kpi-row [data-testid="stHorizontalBlock"] {flex-wrap: wrap;}
        .st-key-kpi-row [data-testid="stColumn"] {
            min-width: min(100%, 205px);
            flex: 1 1 205px;
        }
    }
    @media (max-width: 600px) {
        .table-scroll-hint {display: block; color: #536579; font-size: 0.78rem; margin: 0.5rem 0 0;}
    }
    @media (prefers-reduced-motion: reduce) {
        div[data-testid="stSidebar"] button,
        div[data-testid="stSidebar"] input,
        div[data-testid="stSidebar"] [data-baseweb="select"] > div {
            transition: none;
        }
    }
    </style>
    """,
    unsafe_allow_html=True,
)


def style_chart(figure, height=310):
    """Keep Plotly charts visually consistent without changing their data."""
    figure.update_layout(
        template="plotly_white",
        paper_bgcolor="#FFFFFF",
        plot_bgcolor="#FFFFFF",
        font=dict(
            family="Segoe UI, -apple-system, BlinkMacSystemFont, Arial, sans-serif",
            color=INK,
            size=12,
        ),
        height=height,
        margin=dict(l=18, r=22, t=20, b=30),
        hoverlabel=dict(bgcolor="#FFFFFF", font_color=INK),
        showlegend=False,
    )
    figure.update_xaxes(
        showline=False, zeroline=False, showgrid=False,
        tickfont=dict(color=MUTED), automargin=True,
    )
    figure.update_yaxes(
        showline=False, zeroline=False, gridcolor=GRID,
        tickfont=dict(color=MUTED), automargin=True,
    )
    return figure


@st.cache_data(ttl=300)
def _cached_query(sql, parameters, warehouse_version):
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


def run_query(sql, parameters=()):
    # A replaced warehouse has a new file version, so cached queries refresh.
    version = DATABASE_FILE.stat().st_mtime_ns
    return _cached_query(sql, tuple(parameters), version)


if not DATABASE_FILE.exists():
    st.error(
        "The project warehouse is unavailable. Run the pipeline, "
        "then refresh this page."
    )
    st.stop()


try:
    date_limits = run_query(
    """
    select
        min(pickup_date) as minimum_date,
        max(pickup_date) as maximum_date
    from main.fact_trips
    """
    )
except (duckdb.Error, OSError) as error:
    st.error(f"The project warehouse could not be read: {error}")
    st.stop()

minimum_date = date_limits.loc[0, "minimum_date"]
maximum_date = date_limits.loc[0, "maximum_date"]

if pd.isna(minimum_date) or pd.isna(maximum_date):
    st.info("The warehouse has no accepted trips to display yet.")
    st.stop()


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


st.sidebar.markdown("### Filters")
st.sidebar.caption("January-June 2025 · pickup records")

if "pickup_dates" not in st.session_state:
    st.session_state.pickup_dates = (minimum_date, maximum_date)
if "pickup_borough" not in st.session_state:
    st.session_state.pickup_borough = "All boroughs"


def reset_filters():
    st.session_state.pickup_dates = (minimum_date, maximum_date)
    st.session_state.pickup_borough = "All boroughs"

selected_dates = st.sidebar.date_input(
    "Pickup date range",
    key="pickup_dates",
    min_value=minimum_date,
    max_value=maximum_date,
)

selected_borough = st.sidebar.selectbox(
    "Pickup borough",
    borough_options,
    key="pickup_borough",
)
st.sidebar.button("Reset filters", on_click=reset_filters, use_container_width=True)

if isinstance(selected_dates, tuple):
    if not selected_dates:
        st.info("Choose a pickup date to view the dashboard.")
        st.stop()
    start_date = selected_dates[0]

    if len(selected_dates) == 2:
        end_date = selected_dates[1]
    else:
        end_date = selected_dates[0]
else:
    start_date = selected_dates
    end_date = selected_dates

st.sidebar.caption(
    f"Showing {start_date:%d %b} – {end_date:%d %b} · {selected_borough}"
)

st.markdown(
    f"""
    <div class="taxi-header">
      <p class="eyebrow">NYC YELLOW TAXI</p>
      <h1>Trip Analytics</h1>
      <p class="subtitle">Trip demand, passenger charges, and pickup patterns.</p>
      <div class="scope-badges">
        <span class="scope-badge">{start_date:%d %b %Y} – {end_date:%d %b %Y}</span>
        <span class="scope-badge">Pickup: {html.escape(selected_borough)}</span>
      </div>
    </div>
    """,
    unsafe_allow_html=True,
)
st.markdown(
    '<p class="metric-note">Standard metrics exclude trips with missing or '
    'negative fare or total amounts.</p>',
    unsafe_allow_html=True,
)
with st.expander("About these metrics"):
    st.markdown(
        """
        - **Eligible trips** count accepted trips with non-missing,
          non-negative fare and total amounts. Zero amounts remain eligible.
        - **Recorded charges** are passenger charges, not profit.
          Cash tips are not captured in the source tip field.
        - **Average distance** excludes zero-distance trips and trips
          over 100 miles. **Average duration** excludes trips over six hours.
        - The heatmap shows total trips over the selected period;
          weekdays can occur different numbers of times.
        - Payment code 0 is shown as **Flex Fare trip**.
        """
    )


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
    st.info(
        "No eligible trips match this selection. Try a wider date range "
        "or choose All boroughs."
    )
    st.stop()


def display_number(value, pattern, unit=""):
    return "—" if pd.isna(value) else pattern.format(value) + unit


def compact_charges(value):
    if pd.isna(value):
        return "—"
    if abs(value) >= 1_000_000:
        return f"${value / 1_000_000:,.2f}M"
    return f"${value:,.2f}"


charges = metrics.loc[0, "total_revenue"]
with st.container(key="kpi-row"):
    metric_columns = st.columns(5, gap="small")
    with metric_columns[0].container(key="kpi-trips"):
        st.metric(
            "Eligible trips",
            display_number(metrics.loc[0, "total_trips"], "{:,.0f}"),
            help="Accepted trips with non-missing, non-negative fare and total amounts.",
        )
    with metric_columns[1].container(key="kpi-charges"):
        st.metric(
            "Recorded charges",
            compact_charges(charges),
            help=(
                f"Exact recorded charges: ${charges:,.2f}. "
                "Passenger charges among eligible trips; not profit."
            ),
        )
    with metric_columns[2].container(key="kpi-fare"):
        st.metric(
            "Average fare",
            display_number(metrics.loc[0, "average_fare"], "$" + "{:,.2f}"),
            help="Average fare_amount among eligible trips.",
        )
    with metric_columns[3].container(key="kpi-distance"):
        st.metric(
            "Average distance",
            display_number(metrics.loc[0, "average_distance"], "{:,.2f}", " mi"),
            help="Excludes zero-distance trips and trips over 100 miles.",
        )
    with metric_columns[4].container(key="kpi-duration"):
        st.metric(
            "Average duration",
            display_number(metrics.loc[0, "average_duration"], "{:,.1f}", " min"),
            help="Excludes trips longer than six hours.",
        )


st.markdown("### Daily activity")

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
    st.markdown("**Trips by pickup date**")

    daily_trip_figure = px.line(
        daily_data,
        x="pickup_date",
        y="trip_count",
        markers=True,
        color_discrete_sequence=[BLUE],
        labels={
            "pickup_date": "Pickup date",
            "trip_count": "Trips",
        },
    )

    style_chart(daily_trip_figure, height=300)
    daily_trip_figure.update_traces(
        line=dict(width=2.3),
        marker=dict(size=5),
        hovertemplate="%{x|%b %d, %Y}<br>%{y:,.0f} trips<extra></extra>",
    )
    daily_trip_figure.update_xaxes(title=None, tickformat="%b %d")
    daily_trip_figure.update_yaxes(title=None, rangemode="tozero", tickformat="~s")

    st.plotly_chart(
        daily_trip_figure,
        config=PLOT_CONFIG,
    )

with right_chart:
    st.markdown("**Recorded charges by pickup date**")

    daily_revenue_figure = px.line(
        daily_data,
        markers=True,
        color_discrete_sequence=[TEAL],
        x="pickup_date",
        y="total_revenue",
        labels={
            "pickup_date": "Pickup date",
            "total_revenue": "Recorded charges (USD)",
        },
    )

    style_chart(daily_revenue_figure, height=300)
    daily_revenue_figure.update_traces(
        line=dict(width=2.3),
        marker=dict(size=5),
        hovertemplate="%{x|%b %d, %Y}<br>$%{y:,.2f} recorded charges<extra></extra>",
    )
    daily_revenue_figure.update_xaxes(title=None, tickformat="%b %d")
    daily_revenue_figure.update_yaxes(
        title=None, rangemode="tozero", tickprefix="$", tickformat="~s",
    )

    st.plotly_chart(
        daily_revenue_figure,
        config=PLOT_CONFIG,
    )


st.markdown("### When trips happen")

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
    index=weekday_order,
    columns=range(24),
)

hourly_pivot = hourly_pivot.fillna(0)


st.markdown("**Total trips by weekday and pickup hour**")
st.caption(
    "Each cell totals trips across the selected dates. The number of "
    "occurrences of each weekday can differ within that period."
)

heatmap = px.imshow(
    hourly_pivot,
    aspect="auto",
    color_continuous_scale=[
        [0, "#EFF5FB"], [0.3, "#C4E1E5"], [0.62, "#70B8BF"],
        [0.82, TEAL], [1, NAVY],
    ],
    zmin=0,
    labels={
        "x": "Pickup hour",
        "y": "Weekday",
        "color": "Trips",
    },
)
style_chart(heatmap, height=350)
heatmap.update_layout(margin=dict(l=18, r=22, t=44, b=30))
heatmap.update_traces(
    hovertemplate="%{y} · %{x}:00<br>%{z:,.0f} trips<extra></extra>",
)
heatmap.update_xaxes(title=None, dtick=4)
heatmap.update_yaxes(title=None, showgrid=False)

st.plotly_chart(
    heatmap,
    config=PLOT_CONFIG,
)


st.markdown("### Pickup locations")

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
        pickup_location_id,
        pickup_zone,
        pickup_borough,
        count(*) as trip_count,
        sum(total_amount) as total_revenue
    from main.fact_trips
    where {}
    group by
        pickup_location_id,
        pickup_zone,
        pickup_borough
    order by trip_count desc
    limit 10
    """.format(where_clause),
    tuple(query_parameters),
)

left_chart, right_chart = st.columns(2)

with left_chart:
    st.markdown("**Trips by pickup borough**")

    ranked_boroughs = borough_summary.sort_values("trip_count", ascending=True)
    borough_figure = px.bar(
        ranked_boroughs,
        x="trip_count",
        y="pickup_borough",
        orientation="h",
        text=ranked_boroughs["trip_count"].map(lambda count: f"{count:,.0f}"),
        labels={
            "pickup_borough": "Pickup borough",
            "trip_count": "Trips",
        },
    )

    style_chart(borough_figure, height=340)
    borough_figure.update_layout(margin=dict(l=18, r=72, t=48, b=30))
    borough_figure.update_traces(
        marker_color=[
            BOROUGH_COLORS.get(borough, SLATE)
            for borough in ranked_boroughs["pickup_borough"]
        ],
        hovertemplate="%{y}<br>%{x:,.0f} trips<extra></extra>",
        textposition="outside",
        textfont=dict(color=INK, size=12),
        cliponaxis=False,
    )
    borough_figure.update_xaxes(
        title=None,
        range=[0, ranked_boroughs["trip_count"].max() * 1.18],
        tickformat="~s",
    )
    borough_figure.update_yaxes(
        title=None,
        showgrid=False,
        categoryorder="array",
        categoryarray=ranked_boroughs["pickup_borough"].tolist(),
    )

    st.plotly_chart(
        borough_figure,
        config=PLOT_CONFIG,
    )

with right_chart:
    st.markdown("**Top 10 pickup zones**")

    repeated_zone_name = zone_summary["pickup_zone"].duplicated(keep=False)
    zone_summary["zone_label"] = zone_summary["pickup_zone"].where(
        ~repeated_zone_name,
        zone_summary["pickup_zone"]
        + " (#" + zone_summary["pickup_location_id"].astype(str) + ")",
    )
    ranked_zones = zone_summary.sort_values("trip_count", ascending=True)
    zone_figure = px.bar(
        ranked_zones,
        x="trip_count",
        y="zone_label",
        orientation="h",
        color_discrete_sequence=[BLUE],
        custom_data=["pickup_zone", "pickup_borough", "pickup_location_id"],
        labels={
            "zone_label": "Pickup zone",
            "trip_count": "Trips",
            "pickup_borough": "Borough",
        },
    )
    style_chart(zone_figure, height=340)
    zone_figure.update_layout(margin=dict(l=18, r=22, t=48, b=30))
    zone_figure.update_traces(
        marker_color=[
            BOROUGH_COLORS.get(borough, SLATE)
            for borough in ranked_zones["pickup_borough"]
        ],
        hovertemplate=(
            "%{customdata[0]} (#%{customdata[2]})<br>%{x:,.0f} trips"
            "<br>Pickup borough: %{customdata[1]}<extra></extra>"
        ),
    )
    zone_figure.update_xaxes(title=None, rangemode="tozero", tickformat="~s")
    zone_figure.update_yaxes(
        title=None,
        showgrid=False,
        categoryorder="array",
        categoryarray=ranked_zones["zone_label"].tolist(),
    )

    st.plotly_chart(
        zone_figure,
        config=PLOT_CONFIG,
    )
    zone_legend = "".join(
        f'<span><i style="background-color: {BOROUGH_COLORS.get(borough, SLATE)}">'
        f'</i>{html.escape(str(borough))}</span>'
        for borough in dict.fromkeys(zone_summary["pickup_borough"])
    )
    st.markdown(
        f'<div class="zone-legend">Zone colors show pickup borough: '
        f'{zone_legend}</div>',
        unsafe_allow_html=True,
    )


st.markdown("### Payment methods")

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
payment_summary["payment_type_name"] = payment_summary[
    "payment_type_name"
].fillna("Not specified")

with st.container(key="payment-chart"):
    st.markdown("**Eligible trips by payment method**")

    ranked_payments = payment_summary.sort_values("trip_count")
    payment_figure = px.bar(
        ranked_payments,
        x="trip_count",
        y="payment_type_name",
        orientation="h",
    )
    style_chart(payment_figure, height=310)
    payment_figure.update_layout(margin=dict(l=18, r=22, t=44, b=30))
    payment_figure.update_traces(
        marker_color=[
            PAYMENT_COLORS.get(method, SLATE)
            for method in ranked_payments["payment_type_name"]
        ],
        hovertemplate="%{y}<br>%{x:,.0f} eligible trips<extra></extra>",
    )
    payment_figure.update_xaxes(title=None, rangemode="tozero", tickformat="~s")
    payment_figure.update_yaxes(title=None, showgrid=False)

    st.plotly_chart(
        payment_figure,
        config=PLOT_CONFIG,
    )

with st.container(key="payment-table"):
    st.markdown("**Payment detail**")

    display_payment_data = payment_summary.copy()

    display_payment_data.columns = [
        "Payment method",
        "Trips",
        "Charges (USD)",
        "Avg. tip (%)",
    ]
    payment_table = display_payment_data.style.apply(
        lambda row: [
            "background-color: #F2F6FA" if row.name % 2 else
            "background-color: #FFFFFF"
            for _ in row
        ],
        axis=1,
    ).set_table_styles(
        [{
            "selector": "th",
            "props": [
                ("background-color", "#E7EFF6"),
                ("color", "#243B52"),
                ("font-weight", "600"),
            ],
        }],
    )
    st.dataframe(
        payment_table,
        width="stretch",
        hide_index=True,
        column_config={
            "Payment method": st.column_config.TextColumn(
                "Payment method", width=150,
            ),
            "Trips": st.column_config.NumberColumn(
                "Trips", width=110, format="localized",
            ),
            "Charges (USD)": st.column_config.NumberColumn(
                "Charges (USD)", width=180, format="dollar",
            ),
            "Avg. tip (%)": st.column_config.NumberColumn(
                "Avg. tip (%)", width=130, format="%.1f%%",
            ),
        },
    )
    st.markdown(
        '<p class="table-scroll-hint">Swipe across the table for all columns.</p>',
        unsafe_allow_html=True,
    )

st.caption(
    "Recorded charges are passenger charges, not profit. "
    "Cash tips are not captured in the source tip field."
)

st.caption(
    "Source: New York City Taxi and Limousine Commission · "
    "January-June 2025 Yellow Taxi Trip Records and Taxi Zone Lookup."
)
