import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
from pathlib import Path
import folium
from streamlit_folium import st_folium

st.set_page_config(page_title="Bus Ticket Intelligence", page_icon="🚌", layout="wide")
# ---------------- CUSTOM DASHBOARD STYLING ----------------

st.markdown("""
<style>
    .block-container {
        padding-top: 2rem;
        padding-bottom: 2rem;
        max-width: 1500px;
    }

    h1 {
        font-size: 2.3rem !important;
        font-weight: 750 !important;
        letter-spacing: -1px;
    }

    h2, h3 {
        font-weight: 650 !important;
    }

    [data-testid="stMetric"] {
        background: linear-gradient(135deg, #252b38, #1d2330);
        border: 1px solid #394253;
        padding: 20px 18px;
        border-radius: 14px;
        box-shadow: 0 4px 12px rgba(0,0,0,0.15);
    }

    [data-testid="stMetricLabel"] {
        font-size: 14px;
        font-weight: 600;
    }

    [data-testid="stMetricValue"] {
        font-size: 27px;
        font-weight: 750;
    }

    div[data-testid="stTabs"] button {
        font-size: 15px;
        font-weight: 600;
    }

    [data-testid="stSidebar"] {
        border-right: 1px solid #343b48;
    }

    div[data-testid="stPlotlyChart"] {
        background: #1d2330;
        border: 1px solid #343b48;
        border-radius: 12px;
        padding: 10px;
    }
</style>
""", unsafe_allow_html=True)

st.title("🚌 Bus Ticket Analytics & Intelligence Dashboard")
st.caption("Explore passenger demand, popular routes, ticket collections and data quality.")

DEFAULT_FILE = Path(__file__).parent.parent / "data" / "bus_tickets_cleaned.csv"

@st.cache_data
def load_csv(file):
    data = pd.read_csv(file)
    for col in ["DateTime"]:
        if col in data.columns:
            data[col] = pd.to_datetime(data[col], errors="coerce")
    for col in ["From Stop", "To Stop", "Route", "Time Period", "Data Quality Flag"]:
        if col in data.columns:
            data[col] = data[col].fillna("Unknown").astype(str)
    return data

# ---------------- CHART STYLING ----------------

px.defaults.template = "plotly_dark"

def style_chart(fig):
    fig.update_layout(
        height=400,
        margin=dict(l=25, r=25, t=65, b=30),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(
            family="Arial",
            size=13,
            color="#E5E7EB"
        ),
        title_font=dict(
            size=17,
            color="#FFFFFF"
        ),
        hoverlabel=dict(
            bgcolor="#252B38",
            font_size=13
        )
    )

    fig.update_xaxes(
        showgrid=True,
        gridcolor="rgba(255,255,255,0.10)"
    )

    fig.update_yaxes(
        showgrid=True,
        gridcolor="rgba(255,255,255,0.10)"
    )

    return fig


# ---------------- MAP LOCATION LOOKUP ----------------


@st.cache_data(ttl=86400, show_spinner=False)
def geocode_stop_locations(stop_names):

    from geopy.geocoders import Nominatim
    from geopy.extra.rate_limiter import RateLimiter

    known_locations = {
        "Supermarket": (17.3392, 76.83518),
        "Central bus stand": (17.3262394, 76.8173203),
        "Cbs": (17.3262394, 76.8173203)
    }

    geolocator = Nominatim(
        user_agent="bus_ticket_intelligence_hackathon"
    )

    geocode = RateLimiter(
        geolocator.geocode,
        min_delay_seconds=1.1,
        max_retries=1
    )

    locations = {}

    for stop in stop_names:

        if stop in known_locations:
            locations[stop] = known_locations[stop]
            continue

        # Try different search names
        search_queries = [
            f"{stop}, Kalaburagi, Karnataka, India",
            f"{stop} bus stop, Kalaburagi, Karnataka, India",
            f"{stop}, Gulbarga, Karnataka, India",
            f"{stop} bus stop, Gulbarga, Karnataka, India"
        ]

        for query in search_queries:
            try:
                result = geocode(
                    query,
                    country_codes="in"
                )

                if result:
                    lat = result.latitude
                    lon = result.longitude

                    # Keep results within Kalaburagi area
                    if (
                        17.20 <= lat <= 17.45
                        and 76.70 <= lon <= 76.95
                    ):
                        locations[stop] = (lat, lon)
                        break

            except Exception:
                continue

    return locations



def prepare_excel(uploaded):
    data = pd.read_excel(uploaded)
    data = data.drop(columns=["Unnamed: 9"], errors="ignore")
    for col in ["From Stop", "To Stop"]:
        data[col] = data[col].astype("string").str.strip().replace({"": pd.NA, "nan": pd.NA, "None": pd.NA})
    data["Date"] = pd.to_datetime(data["Date"], errors="coerce")
    data["Time"] = pd.to_datetime(data["Time"].astype(str), errors="coerce").dt.strftime("%H:%M:%S")
    data["DateTime"] = pd.to_datetime(data["Date"].dt.strftime("%Y-%m-%d") + " " + data["Time"], errors="coerce")
    for col in ["Waybill Number", "Ticket Number", "Total Psgr", "Coll Amt", "Uncoll Amt"]:
        data[col] = pd.to_numeric(data[col], errors="coerce")
    data["Hour"] = data["DateTime"].dt.hour
    data["Time Period"] = pd.cut(data["Hour"], bins=[-1,5,11,16,20,23],
                                 labels=["Night","Morning","Afternoon","Evening","Late Night"])
    data["Route"] = data["From Stop"].fillna("Unknown").astype(str) + " → " + data["To Stop"].fillna("Unknown").astype(str)
    data["Total Amount"] = data["Coll Amt"].fillna(0) + data["Uncoll Amt"].fillna(0)
    data["Data Quality Flag"] = np.select(
        [
            data["To Stop"].isna(),
            data["Total Psgr"].fillna(0).le(0),
            data["Coll Amt"].fillna(0).lt(0) | data["Uncoll Amt"].fillna(0).lt(0),
            data["Coll Amt"].fillna(0).gt(0) & data["Uncoll Amt"].fillna(0).gt(0)
        ],
        ["Missing destination","Zero or negative passengers","Negative amount",
         "Both collected and uncollected amounts present - review"],
        default="OK"
    )
    return data

with st.sidebar:
    st.header("Data")
    uploaded = st.file_uploader("Upload bus ticket Excel file (optional)", type=["xlsx"])
    st.caption("If no file is uploaded, the supplied hackathon dataset is loaded automatically.")

if uploaded is not None:
    df = prepare_excel(uploaded)
else:
    if not DEFAULT_FILE.exists():
        st.error("Default dataset not found. Upload the Excel workbook in the sidebar.")
        st.stop()
    df = load_csv(DEFAULT_FILE)

required = ["Total Psgr", "Coll Amt", "Uncoll Amt", "From Stop", "To Stop", "Hour", "Route"]
missing_cols = [c for c in required if c not in df.columns]
if missing_cols:
    st.error("The dataset is missing required columns: " + ", ".join(missing_cols))
    st.stop()

# Sidebar filters
with st.sidebar:
    st.divider()
    st.header("Filters")
    from_options = sorted(df["From Stop"].dropna().astype(str).unique().tolist())
    to_options = sorted(df["To Stop"].dropna().astype(str).unique().tolist())
    selected_from = st.multiselect("Boarding stop", from_options)
    selected_to = st.multiselect("Destination", to_options)
    periods = [x for x in df["Time Period"].dropna().astype(str).unique()] if "Time Period" in df else []
    selected_periods = st.multiselect("Time period", periods)

filtered = df.copy()
if selected_from:
    filtered = filtered[filtered["From Stop"].astype(str).isin(selected_from)]
if selected_to:
    filtered = filtered[filtered["To Stop"].astype(str).isin(selected_to)]
if selected_periods:
    filtered = filtered[filtered["Time Period"].astype(str).isin(selected_periods)]

if filtered.empty:
    st.warning("No records match the selected filters. Change or clear the filters.")
    st.stop()

# KPI calculations
total_passengers = filtered["Total Psgr"].fillna(0).sum()
transactions = len(filtered)
collected = filtered["Coll Amt"].fillna(0).sum()
uncollected = filtered["Uncoll Amt"].fillna(0).sum()
waybills = filtered["Waybill Number"].nunique() if "Waybill Number" in filtered else 0

# k1,k2,k3,k4,k5 = st.columns(5)
# k1.metric("Passengers", f"{total_passengers:,.0f}")
# k2.metric("Ticket transactions", f"{transactions:,.0f}")
# k3.metric("Collected amount", f"₹{collected:,.0f}")
# k4.metric("Uncollected amount", f"₹{uncollected:,.0f}")
# k5.metric("Waybills", f"{waybills:,.0f}")

st.markdown("### 📊 Key Performance Indicators")

k1, k2, k3, k4, k5 = st.columns(5)

with k1:
    st.metric("👥 Passengers", f"{total_passengers:,.0f}")

with k2:
    st.metric("🎫 Transactions", f"{transactions:,.0f}")

with k3:
    st.metric("💰 Collected", f"₹{collected:,.0f}")

with k4:
    st.metric("⏳ Uncollected", f"₹{uncollected:,.0f}")

with k5:
    st.metric("🚌 Waybills", f"{waybills:,.0f}")

overview, routes, intelligence, records = st.tabs(
    ["📊 Overview", "🛣️ Route analysis", "🧠 Intelligent insights", "🔎 Data explorer"]
)

with overview:
    left, right = st.columns(2)
    hourly = filtered.groupby("Hour", dropna=True).agg(
        Passengers=("Total Psgr","sum"),
        Transactions=("Ticket Number","count")
    ).reset_index().sort_values("Hour")
    with left:
        st.subheader("Passenger demand by hour")
        if not hourly.empty:
            fig = px.line(hourly, x="Hour", y="Passengers", markers=True,
                          title="Passengers across the day")
            fig.update_xaxes(dtick=1)
            st.plotly_chart(fig, use_container_width=True)
    with right:
        # st.subheader("Top boarding stops")
        # top_from = filtered.groupby("From Stop", dropna=False)["Total Psgr"].sum().nlargest(10).reset_index()
        # fig = px.bar(top_from.sort_values("Total Psgr"), x="Total Psgr", y="From Stop",
        #              orientation="h", title="Top 10 boarding stops by passengers")
        # st.plotly_chart(fig, use_container_width=True)
        st.subheader("📍 Top boarding stops")

        top_from = (
            filtered.groupby("From Stop")["Total Psgr"]
            .sum()
            .nlargest(10)
            .reset_index()
            .sort_values("Total Psgr")
        )

        fig = px.bar(
            top_from,
            x="Total Psgr",
            y="From Stop",
            orientation="h",
            text="Total Psgr",
            title="Top 10 Boarding Stops by Passenger Demand",
            color_discrete_sequence=["#38BDF8"]
        )

        # fig.update_traces(
        #     texttemplate="%{text:,.0f}",
        #     textposition="outside"
        # )

        fig.update_traces(
            texttemplate="%{text:,.0f}",
            textposition="inside",
            insidetextanchor="middle",
            textfont=dict(color="white", size=12)
        )

        fig = style_chart(fig)
        st.plotly_chart(fig, use_container_width=True)
    left, right = st.columns(2)
    with left:
        st.subheader("Top destinations")
        top_to = filtered.groupby("To Stop", dropna=False)["Total Psgr"].sum().nlargest(10).reset_index()
        fig = px.bar(top_to.sort_values("Total Psgr"), x="Total Psgr", y="To Stop",
                     orientation="h", title="Top 10 destinations by passengers")
        st.plotly_chart(fig, use_container_width=True)
    with right:
        st.subheader("Collected vs uncollected amount")
        amount_df = pd.DataFrame({"Amount type":["Collected","Uncollected"],
                                  "Amount":[collected,uncollected]})
        fig = px.pie(amount_df, names="Amount type", values="Amount", hole=0.48)
        st.plotly_chart(fig, use_container_width=True)

# with routes:
#     st.subheader("Most-used origin → destination routes")
#     route_summary = filtered.groupby("Route").agg(
#         Passengers=("Total Psgr","sum"),
#         Transactions=("Ticket Number","count")
#     ).reset_index().sort_values("Passengers", ascending=False).head(15)
#     st.dataframe(route_summary, use_container_width=True, hide_index=True)
#     st.subheader("Origin-destination passenger matrix")
#     matrix = filtered.pivot_table(index="From Stop", columns="To Stop",
#                                   values="Total Psgr", aggfunc="sum", fill_value=0)
#     st.dataframe(matrix, use_container_width=True)


with routes:
    st.subheader("🛣️ Route Intelligence & Passenger Movement")
    st.caption("Explore popular routes and passenger movement between stops.")

    # Route summary
    route_summary = (
        filtered.groupby("Route")
        .agg(
            Passengers=("Total Psgr", "sum"),
            Transactions=("Ticket Number", "count")
        )
        .reset_index()
        .sort_values("Passengers", ascending=False)
    )

    # Route KPIs
    c1, c2, c3 = st.columns(3)

    c1.metric("Unique Routes", f"{filtered['Route'].nunique():,}")

    if not route_summary.empty:
        c2.metric("Top Route Passengers",
                  f"{route_summary.iloc[0]['Passengers']:,.0f}")
        c3.metric("Routes Analysed", f"{len(route_summary):,}")

    st.divider()

    # Top 10 route comparison
    st.markdown("### 🏆 Top 10 Routes by Passenger Demand")

    top_routes = (
        route_summary.head(10)
        .sort_values("Passengers")
    )

    if not top_routes.empty:
        fig = px.bar(
            top_routes,
            x="Passengers",
            y="Route",
            orientation="h",
            text="Passengers",
            color_discrete_sequence=["#38BDF8"],
            title="Most Popular Bus Routes"
        )

        fig.update_traces(
            texttemplate="%{text:,.0f}",
            textposition="inside",
            insidetextanchor="middle",
            textfont=dict(color="white", size=12)
        )

        fig = style_chart(fig)
        st.plotly_chart(fig, use_container_width=True)

    st.divider()

    # Complete route table
    st.markdown("### 📋 Route Performance Table")

    st.dataframe(
        route_summary,
        use_container_width=True,
        hide_index=True
    )
    st.dataframe(
        route_summary,
        use_container_width=True,
        hide_index=True
    )
    # st.divider()


    st.divider()

    # ---------------- PASSENGER ROUTE MAP ----------------

    st.markdown("### 🗺️ Kalaburagi Passenger Demand Map")

    st.caption(
        "Geographical view of the 10 highest-volume boarding stops "
        "and 10 highest-volume destinations."
    )

    top_board_map = (
        filtered.groupby("From Stop")["Total Psgr"]
        .sum()
        .nlargest(10)
    )

    top_destination_map = (
        filtered.groupby("To Stop")["Total Psgr"]
        .sum()
        .nlargest(10)
    )

    map_stops = tuple(sorted(
        (set(top_board_map.index.astype(str)) |
         set(top_destination_map.index.astype(str)))
        - {"Unknown", "nan"}
    ))

    with st.spinner("Finding stop locations..."):
        stop_locations = geocode_stop_locations(map_stops)
        st.write(
            f"Locations identified: {len(stop_locations)} out of {len(map_stops)}"
        )
    if stop_locations:

        route_map = folium.Map(
            location=[17.335, 76.83],
            zoom_start=13,
            tiles="OpenStreetMap"
        )
        for stop, coordinates in stop_locations.items():

            boarding_count = float(top_board_map.get(stop, 0))
            destination_count = float(top_destination_map.get(stop, 0))

            if boarding_count > 0 and destination_count > 0:
                marker_color = "#A78BFA"
            elif boarding_count > 0:
                marker_color = "#38BDF8"
            else:
                marker_color = "#F59E0B"

            passenger_count = max(
                boarding_count,
                destination_count
            )

            radius = 6 + min(passenger_count / 500, 10)

            tooltip_text = (
                f"{stop} | "
                f"Boarding: {boarding_count:,.0f} | "
                f"Destination: {destination_count:,.0f}"
            )

            folium.CircleMarker(
                location=coordinates,
                radius=radius,
                color=marker_color,
                fill=True,
                fill_color=marker_color,
                fill_opacity=0.85,
                tooltip=tooltip_text
            ).add_to(route_map)

        st_folium(
            route_map,
            width=1200,
            height=550
        )

        st.markdown("""
        <div style="display:flex; gap:22px; flex-wrap:wrap;">
            <span style="color:#38BDF8;">● Boarding stop</span>
            <span style="color:#F59E0B;">● Destination</span>
            <span style="color:#A78BFA;">● Both</span>
        </div>
        """, unsafe_allow_html=True)

        st.caption(
            "Marker size represents passenger volume. Hover over a marker "
            "to view boarding and destination counts. Locations are "
            "geocoded landmarks, not verified bus-stop GPS coordinates."
        )

    else:
        st.warning(
            "No stop locations could be identified. "
            "Please check your internet connection or stop names."
        )

    st.divider()


    # Origin destination matrix
    st.markdown("### 🔥 Origin–Destination Passenger Heatmap")

    st.caption(
        "Showing the 10 highest-volume boarding stops and "
        "10 highest-volume destinations."
    )

    top_origins = (
        filtered.groupby("From Stop")["Total Psgr"]
        .sum()
        .nlargest(10)
        .index
    )

    top_destinations = (
        filtered.groupby("To Stop")["Total Psgr"]
        .sum()
        .nlargest(10)
        .index
    )

    matrix_data = filtered[
        filtered["From Stop"].isin(top_origins)
        & filtered["To Stop"].isin(top_destinations)
    ]

    matrix = matrix_data.pivot_table(
        index="From Stop",
        columns="To Stop",
        values="Total Psgr",
        aggfunc="sum",
        fill_value=0
    )

    if not matrix.empty:
        # fig = px.imshow(
        #     matrix,
        #     labels=dict(
        #         x="Destination",
        #         y="Boarding Stop",
        #         color="Passengers"
        #     ),
        #     color_continuous_scale="Blues",
        #     aspect="auto",
        #     title="Passenger Movement Between Major Stops"
        # )
        fig = px.imshow(
            matrix,
            labels=dict(
                x="Destination",
                y="Boarding Stop",
                color="Passengers"
            ),
            color_continuous_scale="Blues",
            aspect="auto",
            text_auto=".0f",
            title="Passenger Movement Between Major Stops"
        )

        fig.update_traces(
            textfont_size=11
        )

        fig.update_layout(
            height=600,
            xaxis_title="Destination",
            yaxis_title="Boarding Stop"
        )

        fig.update_layout(height=550)
        st.plotly_chart(fig, use_container_width=True)

    st.caption(
        "The heatmap displays passenger counts for the selected major stops. "
        "It does not represent geographical distance or actual bus routes."
    )


# with intelligence:
#     st.subheader("Automatically generated findings")
#     hourly_all = filtered.groupby("Hour")["Total Psgr"].sum().dropna()
#     if not hourly_all.empty:
#         peak_hour = int(hourly_all.idxmax())
#         peak_count = int(hourly_all.max())
#         st.info(f"🕒 Peak demand in the selected data is at {peak_hour:02d}:00, with {peak_count:,} passengers.")
#     top_board = filtered.groupby("From Stop")["Total Psgr"].sum().sort_values(ascending=False)
#     if not top_board.empty:
#         st.success(f"📍 Highest-volume boarding stop: {top_board.index[0]} ({top_board.iloc[0]:,.0f} passengers).")
#     top_dest = filtered.groupby("To Stop")["Total Psgr"].sum().sort_values(ascending=False)
#     if not top_dest.empty:
#         st.success(f"🎯 Highest-volume destination: {top_dest.index[0]} ({top_dest.iloc[0]:,.0f} passengers).")
#     st.warning("Operational recommendation: review service frequency and vehicle capacity around high-demand periods and stops. This dataset alone does not prove overcrowding.")
#     st.caption("These are descriptive insights from the selected records, not predictions. The supplied workbook covers one day.")

#     st.subheader("Data quality checks")
#     if "Data Quality Flag" in filtered:
#         quality = filtered["Data Quality Flag"].value_counts().rename_axis("Issue").reset_index(name="Rows")
#         st.dataframe(quality, use_container_width=True, hide_index=True)
#     st.caption("Rows flagged for review are not automatically fraud. Confirm ticketing rules with the transport authority.")


with intelligence:
    st.subheader("🧠 Intelligent Analytics & Insights")
    st.caption(
        "Automatically generated observations based on the selected bus ticket records."
    )

    # 1. Peak passenger demand
    hourly_all = (
        filtered.groupby("Hour")["Total Psgr"]
        .sum()
        .dropna()
    )

    st.markdown("### 🕒 Passenger Demand Analysis")

    if not hourly_all.empty:
        peak_hour = int(hourly_all.idxmax())
        peak_count = int(hourly_all.max())
        average_hourly = hourly_all.mean()

        c1, c2, c3 = st.columns(3)

        c1.metric("Peak Demand Hour", f"{peak_hour:02d}:00")
        c2.metric("Passengers at Peak", f"{peak_count:,}")
        c3.metric("Average Hourly Passengers", f"{average_hourly:,.0f}")

        if peak_count > average_hourly:
            st.info(
                f"💡 **Insight:** Passenger demand reaches its highest level "
                f"at {peak_hour:02d}:00, with {peak_count:,} passengers."
            )

    st.divider()

    # 2. Boarding stop analysis
    st.markdown("### 📍 Boarding Stop Intelligence")

    boarding_summary = (
        filtered.groupby("From Stop")["Total Psgr"]
        .sum()
        .sort_values(ascending=False)
    )

    if not boarding_summary.empty:
        busiest_stop = boarding_summary.index[0]
        busiest_count = boarding_summary.iloc[0]

        st.success(
            f"**Highest-demand boarding stop:** {busiest_stop} "
            f"with {busiest_count:,.0f} passengers."
        )

    # 3. Destination analysis
    st.markdown("### 🎯 Destination Intelligence")

    destination_summary = (
        filtered.groupby("To Stop")["Total Psgr"]
        .sum()
        .sort_values(ascending=False)
    )

    if not destination_summary.empty:
        popular_destination = destination_summary.index[0]
        destination_count = destination_summary.iloc[0]

        st.info(
            f"**Most popular destination:** {popular_destination} "
            f"with {destination_count:,.0f} passengers."
        )

    st.divider()

    # 4. Route analysis
    st.markdown("### 🛣️ Route Intelligence")

    route_summary = (
        filtered.groupby("Route")
        .agg(
            Passengers=("Total Psgr", "sum"),
            Transactions=("Ticket Number", "count")
        )
        .sort_values("Passengers", ascending=False)
    )

    if not route_summary.empty:
        popular_route = route_summary.index[0]
        route_passengers = route_summary.iloc[0]["Passengers"]

        st.success(
            f"**Highest passenger-volume route:** {popular_route} "
            f"with {route_passengers:,.0f} passengers."
        )

    st.divider()

    # 5. Collection analysis
    st.markdown("### 💰 Ticket Collection Analysis")

    total_recorded_amount = collected + uncollected

    if total_recorded_amount > 0:
        collected_share = collected / total_recorded_amount * 100
        uncollected_share = uncollected / total_recorded_amount * 100

        c1, c2 = st.columns(2)

        c1.metric("Collected Amount Share", f"{collected_share:.1f}%")
        c2.metric("Uncollected Amount Share", f"{uncollected_share:.1f}%")

        st.caption(
            "Shares are calculated from the sum of the recorded collected "
            "and uncollected amounts. They do not establish payment or recovery status."
        )

    st.divider()

    # 6. Automatic operational recommendations
    st.markdown("### 💡 Operational Recommendations")

    if not hourly_all.empty:
        st.info(
            f"🚌 Review bus frequency and vehicle capacity around "
            f"{peak_hour:02d}:00, when passenger demand is highest."
        )

    if not boarding_summary.empty:
        st.info(
            f"📍 Review service availability and passenger facilities "
            f"at {busiest_stop}, the highest-volume boarding stop."
        )

    if not route_summary.empty:
        st.info(
            f"🛣️ Evaluate scheduling and service frequency for "
            f"{popular_route}, the highest passenger-volume route."
        )

    st.caption(
        "Recommendations are based on observed passenger volumes. "
        "Vehicle capacity and actual operating schedules are not available "
        "in this one-day dataset."
    )

    st.divider()

    # 7. Data quality monitoring
    st.markdown("### 🔍 Data Quality Monitoring")

    if "Data Quality Flag" in filtered.columns:
        quality = (
            filtered["Data Quality Flag"]
            .value_counts()
            .rename_axis("Issue")
            .reset_index(name="Number of Records")
        )

        flagged_rows = filtered[
            filtered["Data Quality Flag"] != "OK"
        ].shape[0]

        total_rows = len(filtered)
        clean_rows = total_rows - flagged_rows

        c1, c2, c3 = st.columns(3)

        c1.metric("Total Records", f"{total_rows:,}")
        c2.metric("Records Requiring Review", f"{flagged_rows:,}")
        c3.metric("Records Marked OK", f"{clean_rows:,}")

        st.dataframe(
            quality,
            use_container_width=True,
            hide_index=True
        )

    st.caption(
        "Flagged records require verification. They should not automatically "
        "be interpreted as fraud or misconduct."
    )


# with records:
#     st.subheader("Filtered transaction records")
#     st.dataframe(filtered, use_container_width=True, hide_index=True)
#     csv = filtered.to_csv(index=False).encode("utf-8")
#     st.download_button("⬇️ Download filtered records (CSV)", csv,
#                        file_name="bus_ticket_filtered_records.csv", mime="text/csv")

# st.divider()
# st.caption("Bus Ticket Analytics & Intelligence | Hackathon prototype | One-day dataset")

st.divider()

st.markdown("""
<div style="text-align:center; padding:20px;">

<h3>🚌 Bus Ticket Analytics & Intelligence</h3>

<p style="color:gray;">
Transforming bus ticket records into actionable transport insights.
</p>

<p style="font-size:13px; color:gray;">
Hackathon Project | Developed using Python, Pandas, Plotly & Streamlit
</p>

</div>
""", unsafe_allow_html=True)

with records:
    st.subheader("🔎 Bus Ticket Data Explorer")
    st.caption(
        "Search, inspect and download bus ticket transaction records."
    )

    # Search records
    search_query = st.text_input(
        "🔍 Search records",
        placeholder="Search by stop, route, ticket number, amount..."
    )

    explorer_df = filtered.copy()

    if search_query.strip():
        search_mask = explorer_df.astype(str).apply(
            lambda column: column.str.contains(
                search_query,
                case=False,
                na=False,
                regex=False
            )
        ).any(axis=1)

        explorer_df = explorer_df[search_mask]

    # Display record statistics
    c1, c2, c3 = st.columns(3)

    c1.metric("Matching Records", f"{len(explorer_df):,}")
    c2.metric("Available Columns", f"{len(explorer_df.columns):,}")
    c3.metric("Total Filtered Records", f"{len(filtered):,}")

    st.divider()

    
    # Choose number of records
    display_limit = st.selectbox(
        "Records to display",
        [25, 50, 100, 250, "All"],
        index=1
    )

    if display_limit == "All":
        display_df = explorer_df
    else:
        display_df = explorer_df.head(display_limit)

    st.dataframe(
        display_df,
        use_container_width=True,
        hide_index=True,
        height=500
    )

    if len(explorer_df) > len(display_df):
        st.caption(
            f"Showing {len(display_df):,} of {len(explorer_df):,} matching records. "
            "Download the CSV to access all matching records."
        )

    # Download matching records
    csv = explorer_df.to_csv(index=False).encode("utf-8")

    st.download_button(
        "⬇️ Download matching records (CSV)",
        csv,
        file_name="bus_ticket_filtered_records.csv",
        mime="text/csv"
    )
