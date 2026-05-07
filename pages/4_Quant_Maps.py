from pathlib import Path
import json

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from shared_style import apply_theme


BASE_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = BASE_DIR / "data"
QUANT_DIR = DATA_DIR / "quant"

TRACT_METRICS = QUANT_DIR / "quant_merged_data.csv"
BALTIMORE_TRACTS_GEOJSON = QUANT_DIR / "baltimore_tracts.geojson"

GROUP_COLORS = {
    "Sustained advantage": "#a9c77b",
    "Contemporary advantage": "#f0c56a",
    "Previous advantage": "#e58b60",
    "Sustained disadvantage": "#8f3d46",
    "Excluded from analysis": "#b9b9b9",
}
GROUP_ORDER = [
    "Sustained advantage",
    "Contemporary advantage",
    "Previous advantage",
    "Sustained disadvantage",
    "Excluded from analysis",
]


st.set_page_config(page_title="Quantitative Evidence", layout="wide")
apply_theme()


@st.cache_data(show_spinner=False)
def load_tract_metrics(mtime: float | None = None) -> pd.DataFrame | None:
    if not TRACT_METRICS.exists():
        return None
    df = pd.read_csv(TRACT_METRICS)
    if "GEOID" in df.columns:
        df["GEOID"] = df["GEOID"].astype("string").str.replace(r"\.0$", "", regex=True).str.zfill(11)
    return df


@st.cache_data(show_spinner=False)
def load_geojson(mtime: float | None = None) -> dict | None:
    if not BALTIMORE_TRACTS_GEOJSON.exists():
        return None
    return json.loads(BALTIMORE_TRACTS_GEOJSON.read_text(encoding="utf-8"))


def fmt_money(value: float | int | str) -> str:
    try:
        if pd.isna(value):
            return "NA"
        return f"${float(value):,.0f}"
    except (TypeError, ValueError):
        return "NA"


def file_mtime(path: Path) -> float | None:
    return path.stat().st_mtime if path.exists() else None


def fmt_int(value: float | int | str) -> str:
    try:
        if pd.isna(value):
            return "NA"
        return f"{float(value):,.0f}"
    except (TypeError, ValueError):
        return "NA"


def baltimore_city_tracts(tracts: pd.DataFrame | None) -> pd.DataFrame:
    if tracts is None:
        return pd.DataFrame()
    if "GEOID" in tracts.columns:
        return tracts[tracts["GEOID"].astype(str).str.startswith("24510")].copy()
    return tracts.copy()


def render_metric_cards(tracts: pd.DataFrame | None) -> None:
    if tracts is None:
        st.info(
            "Tract-level metrics file is missing. Add "
            f"`{TRACT_METRICS.name}` under `data/quant/` to show citywide counts and equity totals."
        )
        return

    baltimore = baltimore_city_tracts(tracts)
    if baltimore.empty:
        st.warning("No Baltimore City tracts (GEOID prefix 24510) found in the loaded table.")
        return

    st.markdown("In Baltimore, there are:")
    tangled_sum = baltimore["tangled_properties"].sum(skipna=True) if "tangled_properties" in baltimore.columns else 0
    at_risk_sum = baltimore["at_risk_properties"].sum(skipna=True) if "at_risk_properties" in baltimore.columns else 0
    tangled_net = (
        baltimore["tangled_net_equity"].sum(skipna=True) if "tangled_net_equity" in baltimore.columns else float("nan")
    )
    at_risk_net = (
        baltimore["at_risk_net_equity"].sum(skipna=True) if "at_risk_net_equity" in baltimore.columns else float("nan")
    )

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.metric("Tangled-title properties", fmt_int(tangled_sum))
    with c2:
        st.metric("At-risk properties", fmt_int(at_risk_sum))
    with c3:
        st.metric("Estimated tangled net equity", fmt_money(tangled_net))
    with c4:
        st.metric("Estimated at-risk net equity", fmt_money(at_risk_net))

    gross_tangled = (
        baltimore["tangled_gross_positive_equity"].sum(skipna=True)
        if "tangled_gross_positive_equity" in baltimore.columns
        else float("nan")
    )
    gross_at_risk = (
        baltimore["at_risk_gross_positive_equity"].sum(skipna=True)
        if "at_risk_gross_positive_equity" in baltimore.columns
        else float("nan")
    )
    st.caption(
        f"Gross positive equity (tract sums): tangled-title {fmt_money(gross_tangled)}; "
        f"at-risk {fmt_money(gross_at_risk)}. Net equity can be lower when negative-equity exposure offsets positive."
    )


def render_interactive_map(tracts: pd.DataFrame | None, geojson: dict | None) -> None:
    if tracts is None or geojson is None:
        if tracts is None:
            st.warning("Cannot show the map: tract metrics CSV is missing.")
        else:
            st.warning("Cannot show the map: `baltimore_tracts.geojson` is missing.")
        return
    tract_ids = {
        str(feature.get("properties", {}).get("GEOID", ""))
        for feature in geojson.get("features", [])
    }
    map_data = baltimore_city_tracts(tracts)
    if "GEOID" in map_data.columns and tract_ids:
        map_data = map_data[map_data["GEOID"].astype(str).isin(tract_ids)].copy()
    if map_data.empty:
        st.warning("The tract table and boundary file are loaded, but their GEOIDs do not overlap.")
        return

    st.caption(
        "Choose one tract-level metric at a time. Values are descriptive; they do not imply individual-level causes."
    )
    metric_options = {
        "Tangled-title properties": "tangled_properties",
        "At-risk properties": "at_risk_properties",
        "Tangled / at-risk ratio": "ratio",
        "Tangled net equity": "tangled_net_equity",
        "At-risk net equity": "at_risk_net_equity",
    }
    available = {label: col for label, col in metric_options.items() if col in map_data.columns}
    if not available:
        st.warning("No map metrics found in the tract table.")
        return
    selected_label = st.selectbox("Choose tract metric", list(available.keys()))
    selected_col = available[selected_label]

    hover_data: dict = {}
    if "tangled_properties" in map_data.columns:
        hover_data["tangled_properties"] = ":,.0f"
    if "at_risk_properties" in map_data.columns:
        hover_data["at_risk_properties"] = ":,.0f"
    if "ratio" in map_data.columns:
        hover_data["ratio"] = ":.3f"
    if "intersectionality_group" in map_data.columns:
        hover_data["intersectionality_group"] = True

    map_fig = px.choropleth_map(
        map_data,
        geojson=geojson,
        locations="GEOID",
        featureidkey="properties.GEOID",
        color=selected_col,
        hover_name="GEOID",
        hover_data=hover_data or None,
        color_continuous_scale=["#fff7dc", "#efc267", "#a9c77b", "#294943"],
        map_style="carto-positron",
        center={"lat": 39.299, "lon": -76.61},
        zoom=10,
        opacity=0.78,
        height=560,
    )
    map_fig.update_layout(margin=dict(l=0, r=0, t=0, b=0))
    st.plotly_chart(map_fig, width="stretch")


def render_black_homeownership_chart(tracts: pd.DataFrame | None) -> None:
    if tracts is None:
        st.warning("Cannot show the chart: tract metrics CSV is missing.")
        return
    needed = {"black_population_percentage", "median_property_value_black", "median_property_value_total"}
    if not needed.issubset(tracts.columns):
        st.warning("Required columns for Black homeownership / property value are missing in the tract table.")
        return

    city = baltimore_city_tracts(tracts).copy()
    if city.empty:
        st.warning("No Baltimore City tracts available for the chart.")
        return

    chart_df = city.dropna(
        subset=["black_population_percentage", "median_property_value_black"]
    ).copy()
    if "intersectionality_group" in chart_df.columns:
        chart_df["intersectionality_group"] = chart_df["intersectionality_group"].fillna("Excluded from analysis")

    has_total = "total_properties" in chart_df.columns
    has_tangled = "tangled_properties" in chart_df.columns

    if has_total:
        tangled = (
            chart_df["tangled_properties"].fillna(0).astype(float)
            if has_tangled
            else pd.Series(0.0, index=chart_df.index, dtype=float)
        )
        denom = chart_df["total_properties"].astype(float)
        chart_df["tangled_per_1000_properties"] = (tangled / denom.where(denom > 0)) * 1000.0
        size_col = "tangled_per_1000_properties"
        size_legend = "Tangled per 1,000 properties"
        plot_df = chart_df.dropna(subset=[size_col]).copy()
        n_dropped = len(chart_df) - len(plot_df)
        if n_dropped:
            st.caption(
                f"{n_dropped} tract(s) omitted from this chart: missing `total_properties` or "
                "`total_properties` ≤ 0 (cannot compute tangled per 1,000 properties)."
            )
    else:
        st.info(
            "`total_properties` (ACS B25003_001 occupied housing units) is missing from the loaded "
            "`quant_merged_data.csv`. Falling back to tangled-title property counts for bubble size. "
            "Re-render `20260507_data_merge.qmd` and reload Streamlit to enable the per-1,000 view."
        )
        if has_tangled:
            chart_df["tangled_count_size"] = chart_df["tangled_properties"].fillna(0).clip(lower=0) + 1
        else:
            chart_df["tangled_count_size"] = 1
        size_col = "tangled_count_size"
        size_legend = "Tangled-title properties"
        plot_df = chart_df

    if plot_df.empty:
        st.warning("No tracts left to plot for the Black population × property value chart.")
        return

    hover_data = {
        "black_population_percentage": ":.1f",
        "median_property_value_black": ":$,.0f",
        "median_property_value_total": ":$,.0f",
    }
    if has_tangled:
        hover_data["tangled_properties"] = ":,.0f"
    if has_total:
        hover_data["total_properties"] = ":,.0f"
        hover_data["tangled_per_1000_properties"] = ":,.2f"
    if "intersectionality_group" in plot_df.columns:
        hover_data["intersectionality_group"] = True
    if size_col not in hover_data:
        hover_data[size_col] = False

    scatter_kwargs: dict = dict(
        data_frame=plot_df,
        x="black_population_percentage",
        y="median_property_value_black",
        size=size_col,
        size_max=28,
        hover_name="GEOID",
        hover_data=hover_data,
        labels={
            "black_population_percentage": "Black population (%)",
            "median_property_value_black": "Median property value, Black applicants (USD)",
            "median_property_value_total": "Median property value, all applicants (USD)",
            "intersectionality_group": "Intersectionality group",
            "tangled_properties": "Tangled-title properties",
            "total_properties": "Total properties (ACS B25003_001)",
            "tangled_per_1000_properties": "Tangled per 1,000 properties",
            "tangled_count_size": size_legend,
        },
    )
    if "intersectionality_group" in chart_df.columns:
        scatter_kwargs["color"] = "intersectionality_group"
        scatter_kwargs["color_discrete_map"] = GROUP_COLORS
        scatter_kwargs["category_orders"] = {"intersectionality_group": GROUP_ORDER}

    fig = px.scatter(**scatter_kwargs)
    fig.update_traces(marker=dict(line=dict(width=1, color="#294943"), opacity=0.85))
    fig.update_layout(
        height=480,
        margin=dict(l=10, r=10, t=10, b=10),
        plot_bgcolor="#fff9e6",
        paper_bgcolor="#fff9e6",
        legend=dict(title="Group", orientation="h", yanchor="bottom", y=-0.25, x=0),
        xaxis=dict(showgrid=True, gridcolor="rgba(41, 73, 67, 0.12)", ticksuffix="%"),
        yaxis=dict(showgrid=True, gridcolor="rgba(41, 73, 67, 0.12)", tickprefix="$", tickformat=",.0f"),
    )
    st.plotly_chart(fig, width="stretch")
    if has_total:
        st.caption(
            "Each dot is a Baltimore City census tract. X = Black population share; Y = FFIEC median "
            "property value for Black applicants; bubble size = tangled-title properties per 1,000 "
            "properties (ACS 2019 5-year B25003_001 occupied housing units as denominator, matching "
            "`20260505_healthoutcomes_explore`). Tracts with missing FFIEC values for Black applicants "
            "are dropped."
        )
    else:
        st.caption(
            "Each dot is a Baltimore City census tract. X = Black population share; Y = FFIEC median "
            "property value for Black applicants; bubble size = tangled-title property count (fallback). "
            "Tracts with missing FFIEC values for Black applicants are dropped."
        )


def render_demographic_property_value_map(
    tracts: pd.DataFrame | None,
    geojson: dict | None,
    metric_options: dict[str, tuple[str, str]],
    selectbox_label: str,
    selectbox_key: str,
    height: int = 460,
) -> None:
    if tracts is None or geojson is None:
        st.warning("Cannot show the map: tract metrics or boundary file is missing.")
        return

    tract_ids = {
        str(feature.get("properties", {}).get("GEOID", ""))
        for feature in geojson.get("features", [])
    }
    map_data = baltimore_city_tracts(tracts)
    if "GEOID" in map_data.columns and tract_ids:
        map_data = map_data[map_data["GEOID"].astype(str).isin(tract_ids)].copy()
    if map_data.empty:
        st.warning("No overlapping tracts to map.")
        return

    available = {label: spec for label, spec in metric_options.items() if spec[0] in map_data.columns}
    if not available:
        st.warning("None of the requested columns are present in the tract table.")
        return

    if len(available) == 1:
        selected_label = next(iter(available))
        st.markdown(f"**{selected_label}**")
    else:
        selected_label = st.selectbox(selectbox_label, list(available.keys()), key=selectbox_key)
    selected_col, axis_unit = available[selected_label]

    hover_data: dict = {}
    if "black_population_percentage" in map_data.columns:
        hover_data["black_population_percentage"] = ":.1f"
    if "median_property_value_total" in map_data.columns:
        hover_data["median_property_value_total"] = ":$,.0f"
    if "median_property_value_black" in map_data.columns:
        hover_data["median_property_value_black"] = ":$,.0f"
    if "intersectionality_group" in map_data.columns:
        hover_data["intersectionality_group"] = True

    if axis_unit == "%":
        scale = ["#fff7dc", "#a9c77b", "#294943"]
    else:
        scale = ["#fff7dc", "#efc267", "#c88f2e", "#294943"]

    map_fig = px.choropleth_map(
        map_data,
        geojson=geojson,
        locations="GEOID",
        featureidkey="properties.GEOID",
        color=selected_col,
        hover_name="GEOID",
        hover_data=hover_data or None,
        color_continuous_scale=scale,
        map_style="carto-positron",
        center={"lat": 39.299, "lon": -76.61},
        zoom=10,
        opacity=0.78,
        height=height,
        labels={
            "black_population_percentage": "Black population (%)",
            "median_property_value_total": "Median property value, all (USD)",
            "median_property_value_black": "Median property value, Black (USD)",
            "intersectionality_group": "Intersectionality group",
        },
    )
    cb = dict(title=selected_label)
    if axis_unit == "%":
        cb["ticksuffix"] = "%"
    else:
        cb["tickprefix"] = "$"
        cb["tickformat"] = ",.0f"
    map_fig.update_layout(margin=dict(l=0, r=0, t=0, b=0), coloraxis_colorbar=cb)
    st.plotly_chart(map_fig, width="stretch")


def render_quadrant_diagram() -> None:
    fig = go.Figure()
    fig.add_shape(type="line", x0=0.5, x1=0.5, y0=0, y1=1, line=dict(color="#294943", width=2))
    fig.add_shape(type="line", x0=0, x1=1, y0=0.5, y1=0.5, line=dict(color="#294943", width=2))
    quadrants = [
        ("Sustained advantage", 0.75, 0.75, "Higher historical + higher current advantage"),
        ("Contemporary advantage", 0.75, 0.25, "Lower historical, higher current advantage"),
        ("Previous advantage", 0.25, 0.75, "Higher historical, lower current advantage"),
        ("Sustained disadvantage", 0.25, 0.25, "Lower historical + lower current advantage"),
    ]
    for group, x, y, note in quadrants:
        fig.add_trace(
            go.Scatter(
                x=[x],
                y=[y],
                mode="markers",
                marker=dict(size=30, color=GROUP_COLORS[group], line=dict(width=2, color="#294943")),
                hovertemplate=f"<b>{group}</b><br>{note}<extra></extra>",
                showlegend=False,
            )
        )
        fig.add_annotation(x=x, y=y + 0.11, text=f"<b>{group}</b>", showarrow=False, font=dict(size=13))
        fig.add_annotation(x=x, y=y - 0.13, text=note, showarrow=False, font=dict(size=11), opacity=0.85)
    fig.update_layout(
        height=460,
        margin=dict(l=20, r=20, t=30, b=20),
        plot_bgcolor="#fff9e6",
        paper_bgcolor="#fff9e6",
        xaxis=dict(
            title="Current neighborhood advantage",
            range=[0, 1],
            tickvals=[0.25, 0.75],
            ticktext=["Lower", "Higher"],
            showgrid=False,
            zeroline=False,
        ),
        yaxis=dict(
            title="Historical neighborhood advantage",
            range=[0, 1],
            tickvals=[0.25, 0.75],
            ticktext=["Lower", "Higher"],
            showgrid=False,
            zeroline=False,
        ),
    )
    st.plotly_chart(fig, width="stretch")


def render_intersectionality_group_map(tracts: pd.DataFrame | None, geojson: dict | None) -> None:
    if tracts is None or geojson is None:
        st.warning("Cannot show the group map: tract metrics or boundary file is missing.")
        return
    if "intersectionality_group" not in tracts.columns:
        st.warning("`intersectionality_group` column is missing from the tract table.")
        return

    tract_ids = {
        str(feature.get("properties", {}).get("GEOID", ""))
        for feature in geojson.get("features", [])
    }
    map_data = baltimore_city_tracts(tracts)
    if "GEOID" in map_data.columns and tract_ids:
        map_data = map_data[map_data["GEOID"].astype(str).isin(tract_ids)].copy()
    if map_data.empty:
        st.warning("No overlapping tracts to map for intersectionality groups.")
        return

    map_data["intersectionality_group"] = map_data["intersectionality_group"].fillna("Excluded from analysis")
    map_data["intersectionality_group"] = pd.Categorical(
        map_data["intersectionality_group"], categories=GROUP_ORDER, ordered=False
    )

    map_fig = px.choropleth_map(
        map_data,
        geojson=geojson,
        locations="GEOID",
        featureidkey="properties.GEOID",
        color="intersectionality_group",
        category_orders={"intersectionality_group": GROUP_ORDER},
        color_discrete_map=GROUP_COLORS,
        hover_name="GEOID",
        hover_data={
            "intersectionality_group": True,
            "tangled_properties": ":,.0f" if "tangled_properties" in map_data.columns else False,
            "at_risk_properties": ":,.0f" if "at_risk_properties" in map_data.columns else False,
        },
        map_style="carto-positron",
        center={"lat": 39.299, "lon": -76.61},
        zoom=10,
        opacity=0.78,
        height=460,
    )
    map_fig.update_layout(
        margin=dict(l=0, r=0, t=0, b=0),
        legend=dict(title="Group", orientation="h", yanchor="bottom", y=-0.15, x=0),
    )
    st.plotly_chart(map_fig, width="stretch")


def render_group_boxplots(tracts: pd.DataFrame | None) -> None:
    if tracts is None:
        st.warning("Cannot show boxplots: tract metrics CSV is missing.")
        return
    if "intersectionality_group" not in tracts.columns:
        st.warning("`intersectionality_group` column is missing from the tract table.")
        return

    city = baltimore_city_tracts(tracts).copy()
    if city.empty:
        st.warning("No Baltimore City tracts available for boxplots.")
        return

    if {"tangled_properties", "total_properties"}.issubset(city.columns):
        denominator = city["total_properties"].where(city["total_properties"] > 0)
        city["tangled_properties_per_1000"] = (
            city["tangled_properties"] / denominator
        ) * 1000
    if {"at_risk_properties", "total_properties"}.issubset(city.columns):
        denominator = city["total_properties"].where(city["total_properties"] > 0)
        city["at_risk_properties_per_1000"] = (
            city["at_risk_properties"] / denominator
        ) * 1000

    metric_options = {
        "Tangled-title properties (count)": ("tangled_properties", "count", ":,.0f"),
        "At-risk properties (count)": ("at_risk_properties", "count", ":,.0f"),
        "Tangled-title properties (per 1,000 properties)": (
            "tangled_properties_per_1000",
            "rate",
            ":,.1f",
        ),
        "At-risk properties (per 1,000 properties)": (
            "at_risk_properties_per_1000",
            "rate",
            ":,.1f",
        ),
        "Tangled / at-risk ratio": ("ratio", "ratio", ":.3f"),
        "Tangled net equity (USD)": ("tangled_net_equity", "$", ":,.0f"),
        "At-risk net equity (USD)": ("at_risk_net_equity", "$", ":,.0f"),
        "Black population (%)": ("black_population_percentage", "%", ":.1f"),
        "Median property value, all (USD)": ("median_property_value_total", "$", ":,.0f"),
        "Median property value, Black (USD)": ("median_property_value_black", "$", ":,.0f"),
    }
    available = {label: spec for label, spec in metric_options.items() if spec[0] in city.columns}
    if not available:
        st.warning("No metrics available for boxplots.")
        return

    selected_label = st.selectbox(
        "Choose metric for the boxplot", list(available.keys()), key="group_boxplot_metric"
    )
    selected_col, axis_unit, _value_fmt = available[selected_label]

    plot_df = city.dropna(subset=["intersectionality_group", selected_col]).copy()
    if plot_df.empty:
        st.warning("No non-missing values to plot for the selected metric.")
        return
    plot_df["intersectionality_group"] = pd.Categorical(
        plot_df["intersectionality_group"], categories=GROUP_ORDER, ordered=True
    )
    plot_df = plot_df.sort_values("intersectionality_group")

    n_total = len(plot_df)
    group_counts = (
        plot_df.groupby("intersectionality_group", observed=True)
        .size()
        .reindex(GROUP_ORDER)
        .fillna(0)
        .astype(int)
    )

    fig = px.box(
        plot_df,
        x="intersectionality_group",
        y=selected_col,
        color="intersectionality_group",
        category_orders={"intersectionality_group": GROUP_ORDER},
        color_discrete_map=GROUP_COLORS,
        points="all",
        hover_data={
            "GEOID": True,
            "intersectionality_group": False,
            selected_col: True,
        },
        labels={
            "intersectionality_group": "Intersectionality group",
            selected_col: selected_label,
        },
        title=f"{selected_label} by intersectionality group (n = {n_total} tracts)",
    )
    fig.update_traces(
        marker=dict(opacity=0.6, size=5, line=dict(width=0.5, color="#294943")),
        boxmean=True,
    )

    yaxis_kwargs: dict = dict(
        title=selected_label,
        showgrid=True,
        gridcolor="rgba(41, 73, 67, 0.12)",
    )
    if axis_unit == "%":
        yaxis_kwargs["ticksuffix"] = "%"
        yaxis_kwargs["tickformat"] = ".1f"
    elif axis_unit == "$":
        yaxis_kwargs["tickprefix"] = "$"
        yaxis_kwargs["tickformat"] = ",.0f"
    elif axis_unit == "count":
        yaxis_kwargs["tickformat"] = ",.0f"
    elif axis_unit == "rate":
        yaxis_kwargs["tickformat"] = ",.1f"
    elif axis_unit == "ratio":
        yaxis_kwargs["tickformat"] = ".2f"

    xaxis_ticktext = [
        f"{group}<br><span style='font-size:11px;color:#5d6a64'>n={group_counts[group]}</span>"
        for group in GROUP_ORDER
    ]
    fig.update_layout(
        height=520,
        margin=dict(l=10, r=10, t=70, b=10),
        plot_bgcolor="#fff9e6",
        paper_bgcolor="#fff9e6",
        showlegend=False,
        title=dict(x=0.0, xanchor="left", font=dict(size=16, color="#18312d")),
        xaxis=dict(
            title="",
            showgrid=False,
            tickmode="array",
            tickvals=GROUP_ORDER,
            ticktext=xaxis_ticktext,
        ),
        yaxis=yaxis_kwargs,
    )
    st.plotly_chart(fig, width="stretch")
    st.caption(
        f"Box = IQR with median line; dashed mark = mean. Each dot is a Baltimore City census tract; "
        f"y-axis shows {selected_label.lower()}. Tracts with missing values for the selected metric "
        "are dropped before counting."
    )


tracts = load_tract_metrics(file_mtime(TRACT_METRICS))
geojson = load_geojson(file_mtime(BALTIMORE_TRACTS_GEOJSON))

st.title("Quantitative Evidence")
st.markdown(
    "Tract-level descriptive evidence for tangled-title and at-risk property burden in Baltimore City."
)
st.caption(
    "Data vintage: merged intersectionality tract metrics (`quant_merged_data.csv`); "
    "tract boundaries from `baltimore_tracts.geojson`."
)

st.markdown("## Research Questions")
st.caption(
    "Three quantitative research questions guide this section. RQ1 establishes baseline property "
    "wealth at risk, RQ2 maps tangled-title burden alongside intersectional neighborhood context, "
    "and RQ3 is a backup analysis on mortgage access."
)
rq_cards = [
    (
        "RQ1",
        "Black homeownership and property value",
        "What is the distribution of Black homeownership in Baltimore, and among Black homeowners "
        "what is the median property value (including Black–White gaps)?",
    ),
    (
        "RQ2",
        "Tangled-title concentration and intersectionality",
        "In which Baltimore census tracts are tangled-title and at-risk properties concentrated, "
        "and what is the effect of historical redlining and contemporary segregation on these outcomes?",
    ),
    (
        "RQ3",
        "Mortgage access and interest rates (optional)",
        "How accessible are mortgage loans and at what cost (interest rates), and which areas appear "
        "at higher tangled-title risk when homeownership, mortgage access, and property value are combined?",
    ),
]
rq_cols = st.columns(3)
for column, (tag, title, question) in zip(rq_cols, rq_cards):
    with column:
        st.markdown(
            f"""
            <div class="soft-card rq-card">
            <span class="rq-badge">{tag}</span>
            <h3>{title}</h3>
            <p>{question}</p>
            </div>
            """,
            unsafe_allow_html=True,
        )

st.markdown("## Key Quantitative Takeaways")
# TODO: Replace placeholder with narrative bullets once RQ1/RQ2 analysis is finalized.
st.markdown(
    """
    <div class="soft-card">
    <p><strong>Coming soon</strong> — narrative takeaways will be added once RQ1/RQ2 analysis is finalized.</p>
    </div>
    """,
    unsafe_allow_html=True,
)

st.markdown("## Burden and Equity Evidence")
render_metric_cards(tracts)

st.markdown("## Interactive Tract Explorer")
render_interactive_map(tracts, geojson)

st.markdown("## Black Homeownership and Property Value")

st.markdown("#### Map view: Black population and median property value")
st.caption(
    "Left: Black population share by tract. Right: FFIEC HMDA median property value, with a toggle "
    "between all applicants and Black applicants."
)
left_map, right_map = st.columns(2)
with left_map:
    render_demographic_property_value_map(
        tracts,
        geojson,
        metric_options={
            "Black population (%)": ("black_population_percentage", "%"),
        },
        selectbox_label="Demographic metric",
        selectbox_key="demo_metric_left",
    )
with right_map:
    render_demographic_property_value_map(
        tracts,
        geojson,
        metric_options={
            "Median property value, all applicants (USD)": ("median_property_value_total", "$"),
            "Median property value, Black applicants (USD)": ("median_property_value_black", "$"),
        },
        selectbox_label="Property value metric",
        selectbox_key="pv_metric_right",
    )

st.markdown(
    "Tract-level relationship between **Black population share** and **median property value for "
    "Black applicants** (FFIEC HMDA). Bubble size reflects **tangled-title properties per 1,000 properties** "
    "(ACS 2019 5-year B25003_001 occupied housing units as denominator); color marks the intersectionality group. "
    "Use this to read RQ1 — baseline Black property wealth at risk — alongside the tangled-title burden seen above."
)
render_black_homeownership_chart(tracts)

st.markdown("## Intersectionality Group Context")
st.markdown(
    "Each Baltimore census tract is classified into one of four neighborhood groups by combining "
    "**historical** advantage (e.g., redlining legacy) with **contemporary** advantage (e.g., ICE-based "
    "segregation indicators), following the Uzzi et al. (2023) intersectionality framework. The "
    "diagram on the left explains the 2x2 logic; the map on the right shows how the groups are "
    "distributed across the city."
)
group_left, group_right = st.columns(2)
with group_left:
    st.markdown("#### Conceptual 2x2")
    render_quadrant_diagram()
with group_right:
    st.markdown("#### Tract distribution")
    render_intersectionality_group_map(tracts, geojson)

st.markdown("#### Metric distributions by intersectionality group")
st.caption(
    "Compare how tract-level metrics vary across the four intersectionality groups. Use the dropdown "
    "to switch between burden, equity, demographic, and property-value metrics."
)
render_group_boxplots(tracts)
