import html
import os
import zlib
from pathlib import Path

import duckdb
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
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

# The page reveal plays once per browser session: its CSS is only sent on the
# first script run, so filter changes (reruns) cannot replay it.
FIRST_RUN = "page_revealed" not in st.session_state
st.session_state.page_revealed = True

REVEAL_CSS = """
    @keyframes page-rise {
        from {opacity: 0; transform: translateY(8px);}
        to {opacity: 1; transform: none;}
    }
    @keyframes page-fade {from {opacity: 0;} to {opacity: 1;}}
    [data-testid="stMainBlockContainer"] > [data-testid="stVerticalBlock"] > *:not(:has(.st-key-kpi-row)),
    .st-key-kpi-row [data-testid="stColumn"] {
        animation: page-rise var(--dur-slow) var(--ease-enter) var(--reveal-delay, 300ms) backwards;
    }
    [data-testid="stMainBlockContainer"] > [data-testid="stVerticalBlock"] > *:has(.taxi-header) {--reveal-delay: 0ms;}
    [data-testid="stMainBlockContainer"] > [data-testid="stVerticalBlock"] > *:has(.section-nav) {--reveal-delay: 60ms;}
    .st-key-kpi-row [data-testid="stColumn"]:nth-child(1) {--reveal-delay: 120ms;}
    .st-key-kpi-row [data-testid="stColumn"]:nth-child(2) {--reveal-delay: 180ms;}
    .st-key-kpi-row [data-testid="stColumn"]:nth-child(3) {--reveal-delay: 240ms;}
    .st-key-kpi-row [data-testid="stColumn"]:nth-child(4) {--reveal-delay: 300ms;}
    .st-key-kpi-row [data-testid="stColumn"]:nth-child(5) {--reveal-delay: 360ms;}
    @media (prefers-reduced-motion: reduce) {
        [data-testid="stMainBlockContainer"] > [data-testid="stVerticalBlock"] > *:not(:has(.st-key-kpi-row)),
        .st-key-kpi-row [data-testid="stColumn"] {
            animation-name: page-fade;
            animation-delay: 0ms;
        }
    }
"""

PAGE_CSS = """
    <style>
    :root {
        --dur-fast: 120ms;
        --dur-normal: 200ms;
        --dur-slow: 300ms;
        --ease-enter: cubic-bezier(0, 0, 0.2, 1);
        --ease-exit: cubic-bezier(0.4, 0, 1, 1);
        --ease-standard: cubic-bezier(0.2, 0, 0, 1);
        --focus-ring: #1F4AAE;
        --nav-offset: 3.75rem;
    }
    /* Style-only blocks take no space in the page flow. */
    [data-testid="stLayoutWrapper"]:has(> .st-key-page-style),
    [data-testid="stLayoutWrapper"]:has(> .st-key-reveal-style),
    [data-testid="stLayoutWrapper"]:has(> .st-key-motion-style) {display: none;}
    .block-container {padding-top: 4.5rem; padding-bottom: 2.5rem; max-width: 1380px;}
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
    .taxi-header .hero-top {
        align-items: center;
        display: flex;
        flex-wrap: wrap;
        gap: 0.5rem 1rem;
        justify-content: space-between;
        margin: 0 0 0.5rem;
    }
    .taxi-header .hero-top .eyebrow {margin: 0;}
    .taxi-header .freshness {
        align-items: center;
        background: #1D3147;
        border: 1px solid #40566D;
        border-radius: 999px;
        color: #D9E5EF;
        display: inline-flex;
        font-size: 0.75rem;
        font-weight: 600;
        gap: 0.45rem;
        line-height: 1.3;
        padding: 0.25rem 0.7rem;
    }
    .taxi-header .freshness i {
        background: #5BC7A5;
        border-radius: 50%;
        display: inline-block;
        flex: none;
        height: 0.45rem;
        width: 0.45rem;
    }
    .taxi-header .scope-badges {display: flex; flex-wrap: wrap; gap: 0.5rem; align-items: center;}
    .taxi-header .filter-hint {display: none; color: #E5C176; font-size: 0.8rem; font-weight: 600;}
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
    .metric-note {color: #536579; margin: 0 0 0.3rem; padding-top: 0.6rem;}
    [data-testid="stLayoutWrapper"]:has(> .st-key-section-nav) {
        position: sticky;
        top: var(--nav-offset);
        z-index: 100;
        margin-top: 0.75rem;
    }
    .section-nav {
        background: #FFFFFF;
        border: 1px solid #D7E0E9;
        border-radius: 12px;
        box-shadow: 0 4px 14px rgba(30, 51, 74, 0.08);
        display: flex;
        gap: 0.15rem;
        overflow-x: auto;
        padding: 0.3rem;
    }
    .section-nav a {
        border-radius: 8px;
        color: #243B52;
        flex: none;
        font-size: 0.86rem;
        font-weight: 600;
        padding: 0.35rem 0.8rem;
        text-decoration: none;
        transition: transform var(--dur-fast) var(--ease-standard);
    }
    .section-nav a:hover {background: #E7EFFE; color: #1F4AAE;}
    /* While queries run, a thin line pulses under the nav. It is an overlay,
       so nothing moves; it waits 200 ms so quick updates never flash it. */
    @keyframes loading-pulse {from {opacity: 0.2;} to {opacity: 0.9;}}
    .st-key-section-nav {position: relative;}
    .st-key-section-nav::after {
        background: #356AE6;
        border-radius: 2px;
        bottom: 1px;
        content: "";
        height: 2px;
        left: 12px;
        opacity: 0;
        pointer-events: none;
        position: absolute;
        right: 12px;
    }
    [data-testid="stApp"][data-test-script-state="running"] .st-key-section-nav::after {
        animation: loading-pulse 900ms var(--ease-standard) var(--dur-normal) infinite alternate;
    }
    .section-nav a:active {transform: scale(0.96);}
    [data-testid="stMain"] {scroll-behavior: smooth;}
    .block-container h3 {scroll-margin-top: calc(var(--nav-offset) + 4.25rem);}
    .insight {
        color: #243B52;
        font-size: 0.95rem;
        font-weight: 600;
        margin: -0.55rem 0 0.15rem;
    }
    .metric-defs {display: grid; grid-template-columns: 11rem 1fr; gap: 0.45rem 1rem; margin: 0;}
    .metric-defs dt {color: #172A3B; font-weight: 650;}
    .metric-defs dd {color: #3A4C5F; margin: 0;}
    /* Messages (empty, error) share the card treatment. */
    div[data-testid="stAlert"] {
        border: 1px solid #D7E0E9;
        border-radius: 14px;
        box-shadow: 0 5px 18px rgba(30, 51, 74, 0.055);
        overflow: hidden;
    }
    /* Keyboard focus: 2px ring everywhere in the main area and toolbar. */
    [data-testid="stMain"] a:focus-visible,
    [data-testid="stMain"] button:focus-visible,
    [data-testid="stMain"] summary:focus-visible,
    [data-testid="stMain"] [tabindex="0"]:focus-visible,
    [data-testid="stHeader"] button:focus-visible {
        outline: 2px solid var(--focus-ring);
        outline-offset: 2px;
    }
    /* Plotly's chart toolbar buttons and the scrollable page region. */
    [data-testid="stMain"] .modebar-btn:focus-visible {
        outline: 2px solid var(--focus-ring) !important;
        outline-offset: 1px;
    }
    [data-testid="stMain"]:focus-visible {
        outline: 2px solid var(--focus-ring);
        outline-offset: -2px;
    }
    /* Pressed state for buttons and expander headers. */
    [data-testid="stSidebar"] button:active,
    [data-testid="stMain"] button:active {transform: scale(0.97);}
    [data-testid="stExpander"] summary:active [data-testid="stMarkdownContainer"] {opacity: 0.7;}
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
    [data-testid="stSidebar"] [data-testid="stSidebarContent"] {color: #F2F6FA;}
    [data-testid="stSidebar"] [data-testid="stCaptionContainer"] {color: #D5E0EA;}
    [data-testid="stSidebar"] button,
    [data-testid="stSidebar"] input,
    [data-testid="stSidebar"] [data-baseweb="select"] > div {
        transition: border-color var(--dur-normal) var(--ease-standard),
                    background-color var(--dur-normal) var(--ease-standard),
                    transform var(--dur-fast) var(--ease-standard);
    }
    [data-testid="stSidebar"] button:hover,
    [data-testid="stSidebar"] input:hover,
    [data-testid="stSidebar"] [data-baseweb="select"] > div:hover {
        border-color: #91B2E9;
        background-color: #30465E;
    }
    /* One ring per control: on the field's frame, not the inner input. */
    [data-testid="stSidebar"] button:focus-visible,
    [data-testid="stSidebar"] [data-baseweb="input"]:has(input:focus-visible),
    [data-testid="stSidebar"] [data-baseweb="select"]:focus-within {
        outline: 2px solid #E5C176;
        outline-offset: 2px;
    }
    [data-testid="stSidebar"] input:focus-visible {outline: none;}
    div[data-testid="stMetric"] {
        background: #E7EFFE;
        border: 1px solid #C8D9F7;
        border-top: 3px solid #356AE6;
        border-radius: 14px;
        padding: 0.9rem 0.95rem;
        min-height: 112px;
        position: relative;
        container-type: inline-size;
        box-shadow: 0 4px 14px rgba(30, 51, 74, 0.06);
        transition: transform var(--dur-fast) var(--ease-standard);
    }
    /* Hover lift: the deeper shadow is a separate layer faded by opacity. */
    div[data-testid="stMetric"]::before,
    div[data-testid="stFullScreenFrame"]:has(> [data-testid="stPlotlyChart"])::before {
        border-radius: 14px;
        box-shadow: 0 12px 26px rgba(30, 51, 74, 0.14);
        content: "";
        inset: 0;
        opacity: 0;
        pointer-events: none;
        position: absolute;
        transition: opacity var(--dur-fast) var(--ease-standard);
    }
    div[data-testid="stMetric"]:hover,
    div[data-testid="stFullScreenFrame"]:has(> [data-testid="stPlotlyChart"]):hover {
        transform: translateY(-2px);
    }
    div[data-testid="stMetric"]:hover::before,
    div[data-testid="stFullScreenFrame"]:has(> [data-testid="stPlotlyChart"]):hover::before {
        opacity: 1;
    }
    div[data-testid="stFullScreenFrame"]:has(> [data-testid="stPlotlyChart"]) {
        position: relative;
        transition: transform var(--dur-fast) var(--ease-standard);
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
        /* Scale with the card's own width so values never truncate. */
        font-size: clamp(1.2rem, 14cqi, 2.15rem);
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
    @media (max-width: 1300px) {
        /* Three cards on the first row and two on the second. */
        .st-key-kpi-row [data-testid="stHorizontalBlock"] {flex-wrap: wrap;}
        .st-key-kpi-row [data-testid="stColumn"] {
            min-width: calc(33.333% - 1rem);
            flex: 1 1 calc(33.333% - 1rem);
        }
    }
    @media (max-width: 900px) {
        .block-container {padding: 4.5rem 1rem 2rem;}
        .taxi-header {padding: 1.5rem;}
        .taxi-header h1 {font-size: 1.9rem;}
        div[data-testid="stMetric"] {min-height: 104px;}
        .st-key-kpi-row [data-testid="stHorizontalBlock"] {flex-wrap: wrap;}
        .st-key-kpi-row [data-testid="stColumn"] {
            min-width: min(100%, 205px);
            flex: 1 1 205px;
        }
    }
    @media (max-width: 768px) {
        /* The sidebar is collapsed here, so say where the filters are. */
        .taxi-header .filter-hint {display: inline;}
        .metric-defs {grid-template-columns: 1fr; gap: 0.1rem;}
        .metric-defs dd {margin-bottom: 0.5rem;}
    }
    @media (max-width: 600px) {
        .table-scroll-hint {display: block; color: #536579; font-size: 0.78rem; margin: 0.5rem 0 0;}
        .section-nav a {padding: 0.35rem 0.55rem;}
    }
    @media (prefers-reduced-motion: reduce) {
        [data-testid="stSidebar"] button,
        [data-testid="stSidebar"] input,
        [data-testid="stSidebar"] [data-baseweb="select"] > div,
        .section-nav a,
        div[data-testid="stMetric"],
        div[data-testid="stFullScreenFrame"]:has(> [data-testid="stPlotlyChart"]) {
            transition: none;
        }
        [data-testid="stMain"] {scroll-behavior: auto;}
        div[data-testid="stMetric"]:hover,
        div[data-testid="stFullScreenFrame"]:has(> [data-testid="stPlotlyChart"]):hover,
        [data-testid="stSidebar"] button:active,
        [data-testid="stMain"] button:active,
        .section-nav a:active {
            transform: none;
        }
        [data-testid="stApp"][data-test-script-state="running"] .st-key-section-nav::after {
            animation: none;
            opacity: 0.6;
        }
    }
    </style>
"""

with st.container(key="page-style"):
    st.markdown(PAGE_CSS, unsafe_allow_html=True)
# Kept apart from the page styles: replacing a style block drops its rules
# for a moment, which is harmless here but would unstyle the whole page.
with st.container(key="reveal-style"):
    st.markdown(
        "<style>" + (REVEAL_CSS if FIRST_RUN else "") + "</style>",
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


def share_text(count, total):
    """Percentage of the total, with very small shares shown as <0.1%."""
    share = 100 * count / total if total else 0
    if 0 < share < 0.05:
        return "<0.1%"
    return f"{share:.1f}%"


def trailing_average(daily, column, start, end, window=7):
    """Trailing average over calendar days; days without trips count as zero.

    The first window - 1 days have no value, so short ranges show no average.
    """
    days = pd.date_range(start, end, freq="D")
    series = daily.set_index(pd.to_datetime(daily["pickup_date"]))[column]
    series = series.reindex(days, fill_value=0)
    return series.rolling(window, min_periods=window).mean()


def batch_status_table(batches):
    """One display row per loaded month from the pipeline_batches log."""
    return pd.DataFrame({
        "Month": [
            pd.to_datetime(month + "-01").strftime("%b %Y")
            for month in batches["month"]
        ],
        "Source rows": batches["source_rows"],
        "Accepted rows": batches["accepted_rows"],
        "Rejected rows": batches["rejected_rows"],
        "Reconciles": [
            "Yes" if source == accepted + rejected else "No"
            for source, accepted, rejected in zip(
                batches["source_rows"], batches["accepted_rows"],
                batches["rejected_rows"],
            )
        ],
        "Processed at (UTC)": pd.to_datetime(
            batches["processed_at_utc"]
        ).dt.strftime("%Y-%m-%d %H:%M"),
    })


def batch_summary_text(batches):
    """Header line for the pipeline panel, e.g. '6 monthly batches · all reconcile'."""
    total = len(batches)
    failing = int((
        batches["source_rows"]
        != batches["accepted_rows"] + batches["rejected_rows"]
    ).sum())
    noun = "monthly batch" if total == 1 else "monthly batches"
    if failing == 0:
        verdict = "reconciles" if total == 1 else "all reconcile"
    elif failing == 1:
        verdict = "1 does not reconcile"
    else:
        verdict = f"{failing} do not reconcile"
    return f"{total} {noun} · {verdict}"


def freshness_text(last_month, processed):
    """Hero status pill; empty when the warehouse has no batch log."""
    if processed is None or pd.isna(processed):
        return ""
    return (
        f"Data through {last_month:%b %Y} · "
        f"last batch {processed.day} {processed:%b %Y}"
    )


# Insight lines: one computed fact per section, from the frames the charts use.
# Ties go to the first row in query order (earliest day, lowest hour).
def peak_day_insight(daily):
    row = daily.loc[daily["trip_count"].idxmax()]
    day = pd.to_datetime(row["pickup_date"])
    years = pd.to_datetime(daily["pickup_date"]).dt.year
    year = f" {day:%Y}" if years.nunique() > 1 else ""
    return (
        f"Peak day: {day:%a} {day.day} {day:%b}{year} "
        f"({row['trip_count']:,.0f} trips)"
    )


def busiest_hour_insight(hourly):
    by_hour = hourly.groupby("pickup_hour")["trip_count"].sum().sort_index()
    return f"Busiest pickup hour: {int(by_hour.idxmax()):02d}:00"


def location_insight(boroughs, zones, selected_borough):
    """Top borough share, or the top zone's share once a borough is selected."""
    total = boroughs["trip_count"].sum()
    if selected_borough == "All boroughs":
        top = boroughs.loc[boroughs["trip_count"].idxmax()]
        return (
            f"{top['pickup_borough']}: "
            f"{share_text(top['trip_count'], total)} of eligible pickups"
        )
    top = zones.loc[zones["trip_count"].idxmax()]
    return (
        f"Top pickup zone: {top['pickup_zone']} "
        f"({share_text(top['trip_count'], total)} of eligible "
        f"{selected_borough} pickups)"
    )


def payment_insight(payments):
    top = payments.loc[payments["trip_count"].idxmax()]
    share = share_text(top["trip_count"], payments["trip_count"].sum())
    return f"{top['payment_type_name']}: {share} of eligible trips"


def show_insight(text):
    st.markdown(
        f'<p class="insight">{html.escape(text)}</p>', unsafe_allow_html=True,
    )


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


def loaded_period():
    """Loaded month range from the batch log, else from accepted pickup dates."""

    try:
        batches = run_query(
            """
            select min(month) as first_month, max(month) as last_month,
                max(processed_at_utc) as last_processed
            from main.pipeline_batches
            """
        )
        first = pd.to_datetime(batches.loc[0, "first_month"] + "-01")
        last = pd.to_datetime(batches.loc[0, "last_month"] + "-01")
        processed = batches.loc[0, "last_processed"]
    except (duckdb.Error, OSError, TypeError, ValueError):
        first, last, processed = minimum_date, maximum_date, None
    return f"{first:%b %Y} – {last:%b %Y}", last, processed


period_text, last_month, last_processed = loaded_period()


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
st.sidebar.caption(f"Data loaded: {period_text} · pickup records")

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
if last_processed is not None and not pd.isna(last_processed):
    st.sidebar.caption(f"Last batch processed: {last_processed:%d %b %Y %H:%M} UTC")

freshness = freshness_text(last_month, last_processed)
freshness_pill = (
    f'<span class="freshness"><i></i>{html.escape(freshness)}</span>'
    if freshness else ""
)
st.markdown(
    f"""
    <div class="taxi-header">
      <div class="hero-top">
        <p class="eyebrow">NYC YELLOW TAXI</p>{freshness_pill}
      </div>
      <h1>Trip Analytics</h1>
      <p class="subtitle">Trip demand, passenger charges, and pickup patterns.</p>
      <div class="scope-badges">
        <span class="scope-badge">{start_date:%d %b %Y} – {end_date:%d %b %Y}</span>
        <span class="scope-badge">Pickup: {html.escape(selected_borough)}</span>
        <span class="filter-hint">Change filters: tap » at the top left</span>
      </div>
    </div>
    """,
    unsafe_allow_html=True,
)
with st.container(key="section-nav"):
    st.markdown(
        """
        <nav class="section-nav" aria-label="Dashboard sections">
          <a href="#overview">Overview</a>
          <a href="#when">When</a>
          <a href="#where">Where</a>
          <a href="#payments">Payments</a>
          <a href="#pipeline">Pipeline</a>
        </nav>
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
        <dl class="metric-defs">
          <dt>Eligible trips</dt>
          <dd>Count accepted trips with non-missing, non-negative fare and
            total amounts. Zero amounts remain eligible.</dd>
          <dt>Recorded charges</dt>
          <dd>Passenger charges, not profit. Cash tips are not captured in
            the source tip field.</dd>
          <dt>Average distance</dt>
          <dd>Excludes zero-distance trips and trips over 100 miles.</dd>
          <dt>Average duration</dt>
          <dd>Excludes trips over six hours.</dd>
          <dt>Heatmap</dt>
          <dd>Shows total trips over the selected period; weekdays can occur
            different numbers of times.</dd>
          <dt>Flex Fare trip</dt>
          <dd>Payment code 0 is shown under this name.</dd>
        </dl>
        """,
        unsafe_allow_html=True,
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
kpi_values = {
    "trips": display_number(metrics.loc[0, "total_trips"], "{:,.0f}"),
    "charges": compact_charges(charges),
    "fare": display_number(metrics.loc[0, "average_fare"], "$" + "{:,.2f}"),
    "distance": display_number(metrics.loc[0, "average_distance"], "{:,.2f}", " mi"),
    "duration": display_number(metrics.loc[0, "average_duration"], "{:,.1f}", " min"),
}


def update_motion_css(values, previous_values, filters_changed):
    """CSS for this run's update motion; empty when nothing changed.

    Each KPI value whose text differs from the previous run gets a 200 ms
    highlight, and the charts fade in when the filters changed. Streamlit
    rebuilds these elements on a rerun, so the rule must be absent when
    nothing changed. The animation name carries a checksum of the value so
    a reused element restarts it too. The displayed text is never altered.
    """
    rules = []
    for key, value in values.items():
        if previous_values.get(key, value) == value:
            continue
        name = f"kpi-{key}-{zlib.crc32(value.encode()):08x}"
        target = f'.st-key-kpi-{key} [data-testid="stMetricValue"]'
        rules.append(
            f"@keyframes {name} {{from {{opacity: 0.2; transform: translateY(3px);}} "
            f"to {{opacity: 1; transform: none;}}}}"
            f"@keyframes {name}-fade {{from {{opacity: 0.2;}} to {{opacity: 1;}}}}"
            f"{target} {{animation: {name} var(--dur-normal) var(--ease-enter);}}"
            f"@media (prefers-reduced-motion: reduce) {{"
            f"{target} {{animation-name: {name}-fade;}}}}"
        )
    if filters_changed:
        rules.append(
            "@keyframes chart-update {from {opacity: 0;} to {opacity: 1;}}"
            # Only charts of the current run fade; outgoing ones are stale.
            '[data-testid="stElementContainer"][data-stale="false"] '
            '[data-testid="stPlotlyChart"] .js-plotly-plot '
            "{animation: chart-update var(--dur-normal) var(--ease-enter);}"
        )
    return "<style>" + "".join(rules) + "</style>"


current_filters = (start_date, end_date, selected_borough)
with st.container(key="motion-style"):
    st.markdown(
        update_motion_css(
            kpi_values,
            st.session_state.get("shown_kpi_values", {}),
            st.session_state.get("shown_filters", current_filters) != current_filters,
        ),
        unsafe_allow_html=True,
    )
st.session_state.shown_kpi_values = kpi_values
st.session_state.shown_filters = current_filters

with st.container(key="kpi-row"):
    metric_columns = st.columns(5, gap="small")
    with metric_columns[0].container(key="kpi-trips"):
        st.metric(
            "Eligible trips",
            kpi_values["trips"],
            help="Accepted trips with non-missing, non-negative fare and total amounts.",
        )
    with metric_columns[1].container(key="kpi-charges"):
        st.metric(
            "Recorded charges",
            kpi_values["charges"],
            help=(
                f"Exact recorded charges: ${charges:,.2f}. "
                "Passenger charges among eligible trips; not profit."
            ),
        )
    with metric_columns[2].container(key="kpi-fare"):
        st.metric(
            "Average fare",
            kpi_values["fare"],
            help="Average fare_amount among eligible trips.",
        )
    with metric_columns[3].container(key="kpi-distance"):
        st.metric(
            "Average distance",
            kpi_values["distance"],
            help="Excludes zero-distance trips and trips over 100 miles.",
        )
    with metric_columns[4].container(key="kpi-duration"):
        st.metric(
            "Average duration",
            kpi_values["duration"],
            help="Excludes trips longer than six hours.",
        )


st.subheader("Daily activity", anchor="overview")

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

show_insight(peak_day_insight(daily_data))


def add_trailing_average(figure, column, color, hover_value):
    """Overlay a 7-day trailing average when the range has at least 7 days."""
    average = trailing_average(daily_data, column, start_date, end_date)
    if average.dropna().empty:
        return
    figure.update_traces(name="Daily", opacity=0.55, showlegend=True)
    figure.add_trace(go.Scatter(
        x=list(average.index),
        y=[None if pd.isna(value) else float(value) for value in average],
        mode="lines",
        name="7-day average",
        line=dict(color=color, width=2.6),
        connectgaps=False,
        hovertemplate=(
            "%{x|%b %d, %Y}<br>7-day average: " + hover_value + "<extra></extra>"
        ),
    ))
    figure.update_layout(
        showlegend=True,
        legend=dict(
            orientation="h", x=0, y=1.02, xanchor="left", yanchor="bottom",
            font=dict(color=MUTED, size=11),
        ),
        margin=dict(l=18, r=22, t=36, b=30),
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
        hovertemplate="%{x|%b %d, %Y}<br>Daily: %{y:,.0f} trips<extra></extra>",
    )
    add_trailing_average(daily_trip_figure, "trip_count", "#1F4AAE", "%{y:,.0f} trips")
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
        hovertemplate="%{x|%b %d, %Y}<br>Daily: $%{y:,.2f} recorded charges<extra></extra>",
    )
    add_trailing_average(
        daily_revenue_figure, "total_revenue", "#0B5E5A", "$%{y:,.2f} recorded charges",
    )
    daily_revenue_figure.update_xaxes(title=None, tickformat="%b %d")
    daily_revenue_figure.update_yaxes(
        title=None, rangemode="tozero", tickprefix="$", tickformat="~s",
    )

    st.plotly_chart(
        daily_revenue_figure,
        config=PLOT_CONFIG,
    )


st.subheader("When trips happen", anchor="when")

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

show_insight(busiest_hour_insight(hourly_data))

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
    hovertemplate="%{y} · %{x:02d}:00<br>%{z:,.0f} trips<extra></extra>",
)
heatmap.update_xaxes(
    title=dict(text="Pickup hour", font=dict(color=MUTED, size=12)),
    tickmode="array",
    # Six-hour ticks: four-hour labels collide on phone-width charts.
    tickvals=list(range(0, 24, 6)),
    ticktext=[f"{hour:02d}:00" for hour in range(0, 24, 6)],
    tickangle=0,
    tickfont=dict(color=MUTED, size=11),
)
heatmap.update_yaxes(title=None, showgrid=False)

st.plotly_chart(
    heatmap,
    config=PLOT_CONFIG,
)


st.subheader("Pickup locations", anchor="where")

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

show_insight(location_insight(borough_summary, zone_summary, selected_borough))

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
    zone_figure.update_layout(margin=dict(l=18, r=40, t=48, b=30))
    zone_figure.update_traces(
        marker_color=[
            BOROUGH_COLORS.get(borough, SLATE)
            for borough in ranked_zones["pickup_borough"]
        ],
        hovertemplate=(
            "%{customdata[0]} (#%{customdata[2]})<br>%{x:,.0f} trips"
            "<br>Pickup borough: %{customdata[1]}<extra></extra>"
        ),
        text=ranked_zones["trip_count"].map(lambda count: f"{count:,.0f}"),
        textposition="outside",
        textfont=dict(color=INK, size=12),
        cliponaxis=False,
    )
    zone_figure.update_xaxes(
        title=None,
        range=[0, ranked_zones["trip_count"].max() * 1.3],
        tickformat="~s",
    )
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


st.subheader("Payment methods", anchor="payments")

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

show_insight(payment_insight(payment_summary))

with st.container(key="payment-chart"):
    st.markdown("**Eligible trips by payment method**")

    ranked_payments = payment_summary.sort_values("trip_count")
    payment_figure = px.bar(
        ranked_payments,
        x="trip_count",
        y="payment_type_name",
        orientation="h",
    )
    payment_total = ranked_payments["trip_count"].sum()
    payment_labels = [
        f"{count:,.0f} · {share_text(count, payment_total)}"
        for count in ranked_payments["trip_count"]
    ]
    style_chart(payment_figure, height=310)
    payment_figure.update_layout(margin=dict(l=18, r=72, t=44, b=30))
    payment_figure.update_traces(
        marker_color=[
            PAYMENT_COLORS.get(method, SLATE)
            for method in ranked_payments["payment_type_name"]
        ],
        customdata=[[label] for label in payment_labels],
        hovertemplate="%{y}<br>%{customdata[0]} of eligible trips<extra></extra>",
        text=payment_labels,
        textposition="outside",
        textfont=dict(color=INK, size=12),
        cliponaxis=False,
    )
    payment_figure.update_xaxes(
        title=None,
        range=[0, ranked_payments["trip_count"].max() * 1.3],
        tickformat="~s",
    )
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

# Read-only batch log; independent of the date and borough filters.
st.subheader("Data pipeline", anchor="pipeline")
try:
    batch_log = run_query(
        """
        select month, source_rows, accepted_rows, rejected_rows,
            processed_at_utc
        from main.pipeline_batches
        order by month
        """
    )
except (duckdb.Error, OSError):
    batch_log = None
has_batch_log = batch_log is not None and not batch_log.empty
if has_batch_log:
    show_insight(batch_summary_text(batch_log))

with st.expander("Data pipeline status"):
    if not has_batch_log:
        st.caption("Batch log not available for this warehouse.")
    else:
        st.dataframe(
            batch_status_table(batch_log),
            width="stretch",
            hide_index=True,
            column_config={
                column: st.column_config.NumberColumn(column, format="localized")
                for column in ("Source rows", "Accepted rows", "Rejected rows")
            },
        )
        st.caption(
            "Months are loaded as monthly batches by the Prefect pipeline; "
            "each batch must reconcile before the warehouse is published."
        )

st.caption(
    "Recorded charges are passenger charges, not profit. "
    "Cash tips are not captured in the source tip field."
)

st.caption(
    "Source: New York City Taxi and Limousine Commission · "
    f"{period_text} Yellow Taxi Trip Records and Taxi Zone Lookup."
)
