"""
Side 1: Nabobasert prisanalyse (Price Gap).

Finner boliger som er relativt billige sammenlignet med nabolaget.
"""
from __future__ import annotations

import io
import os
import glob
import math

import branca.colormap as cm
import folium
import numpy as np
import pandas as pd
import streamlit as st
from streamlit_folium import st_folium

from eiendom_analyse_claude.storage.json_store import load_estates
from eiendom_analyse_claude.analysis.price_gap import compute_price_gaps

st.title("📊 Nabobasert Prisgapanalyse")
st.markdown(
    "Finn boliger som er relativt **underpriset** sammenlignet med naboer innen valgt radius."
)

# ---------------------------------------------------------------------------
# Datafil-velger
# ---------------------------------------------------------------------------

data_dir = "Data"
json_files = sorted(glob.glob(os.path.join(data_dir, "*.json"))) if os.path.isdir(data_dir) else []
sales_files = [f for f in json_files if "utleie" not in os.path.basename(f).lower()]

if not sales_files:
    st.error("Ingen salgsdatafiler funnet i `Data/`. Hent data med CLI-verktøyet.")
    st.stop()

selected_file = st.selectbox(
    "Velg datafil",
    sales_files,
    format_func=os.path.basename,
)

# ---------------------------------------------------------------------------
# Last data
# ---------------------------------------------------------------------------

@st.cache_data
def load_df(path: str) -> pd.DataFrame:
    estates = load_estates(path)
    rows = []
    for est in estates.values():
        d = est.to_dict()
        if isinstance(d.get("neighbors"), list):
            d["neighbors"] = ",".join(d["neighbors"])
        rows.append(d)
    return pd.DataFrame(rows)


df_raw = load_df(selected_file)
n_total = len(df_raw)
n_geo = df_raw["latitude"].notna().sum()

st.caption(f"📂 {os.path.basename(selected_file)} — **{n_total}** boliger, **{n_geo}** med koordinater")

# ---------------------------------------------------------------------------
# Filtre
# ---------------------------------------------------------------------------

with st.expander("🔧 Filtre", expanded=True):
    fc1, fc2, fc3 = st.columns(3)

    with fc1:
        price_range = st.slider(
            "Pris (NOK)",
            min_value=0,
            max_value=20_000_000,
            value=(0, 10_000_000),
            step=100_000,
            format="%d",
        )

    with fc2:
        area_range = st.slider(
            "Areal (m²)",
            min_value=0,
            max_value=500,
            value=(0, 300),
            step=5,
        )

    with fc3:
        prop_types = ["Alle"] + sorted(
            df_raw["property_type"].dropna().unique().tolist()
            if "property_type" in df_raw.columns else []
        )
        selected_type = st.selectbox("Boligtype", prop_types)

df_filtered = df_raw.copy()
if "total_price" in df_filtered.columns:
    df_filtered = df_filtered[
        (df_filtered["total_price"].fillna(0) >= price_range[0]) &
        (df_filtered["total_price"].fillna(0) <= price_range[1])
    ]
if "area" in df_filtered.columns:
    df_filtered = df_filtered[
        (df_filtered["area"].fillna(0) >= area_range[0]) &
        (df_filtered["area"].fillna(0) <= area_range[1])
    ]
if selected_type != "Alle" and "property_type" in df_filtered.columns:
    df_filtered = df_filtered[df_filtered["property_type"] == selected_type]

# ---------------------------------------------------------------------------
# Analyse-parametere
# ---------------------------------------------------------------------------

st.subheader("⚙️ Analyseparametere")
c1, c2, c3, c4 = st.columns(4)

with c1:
    radius_m = st.slider("Radius (meter)", 100, 3000, 500, 50)
with c2:
    price_field = st.selectbox("Prisfelt", ["total_price", "asking_price"])
with c3:
    min_neighbors = st.slider("Min naboer", 1, 25, 5)
with c4:
    max_points = st.slider("Maks punkter på kart", 200, 6000, 2500, 100)

# ---------------------------------------------------------------------------
# Beregn gap
# ---------------------------------------------------------------------------

if df_filtered.empty:
    st.warning("Ingen data etter filtrering.")
    st.stop()

df_gap = compute_price_gaps(df_filtered, radius_m=radius_m, price_field=price_field, min_neighbors=min_neighbors)
df_valid = df_gap.dropna(subset=["gap_ppm2"]).sort_values("gap_ppm2", ascending=False)

# ---------------------------------------------------------------------------
# Nøkkeltall
# ---------------------------------------------------------------------------

if not df_valid.empty:
    m1, m2, m3, m4 = st.columns(4)
    with m1:
        st.metric("Analyserte boliger", len(df_valid))
    with m2:
        top_gap = df_valid["gap_ppm2"].iloc[0]
        st.metric("Beste gap (kr/m²)", f"{top_gap:,.0f}")
    with m3:
        top_gap_pct = df_valid["gap_pct"].iloc[0]
        st.metric("Beste gap (%)", f"{top_gap_pct:.1f} %")
    with m4:
        avg_ppm2 = df_valid["own_ppm2"].mean()
        st.metric("Snitt pris/m²", f"{avg_ppm2:,.0f} kr")

# ---------------------------------------------------------------------------
# Rankingtabell
# ---------------------------------------------------------------------------

st.subheader("🏆 Ranking – mest underprisede boliger")

display_cols = [
    c for c in [
        "finnkode", "title", "property_type", "area", "bedrooms",
        "own_ppm2", "neighbor_avg_ppm2", "gap_ppm2", "gap_pct",
        "neighbor_count", "total_price", "asking_price", "location", "url"
    ]
    if c in df_valid.columns
]

st.dataframe(
    df_valid[display_cols].head(200).style.format({
        "own_ppm2": "{:,.0f}",
        "neighbor_avg_ppm2": "{:,.0f}",
        "gap_ppm2": "{:,.0f}",
        "gap_pct": "{:.1f}",
        "total_price": "{:,.0f}",
        "asking_price": "{:,.0f}",
    }, na_rep="—"),
    use_container_width=True,
)

# ---------------------------------------------------------------------------
# Eksport
# ---------------------------------------------------------------------------

st.subheader("📥 Eksporter til Excel")
buf = io.BytesIO()
with pd.ExcelWriter(buf, engine="openpyxl") as writer:
    df_gap.to_excel(writer, index=False, sheet_name="alle_boliger")
    df_valid.to_excel(writer, index=False, sheet_name="rangert")
st.download_button(
    "Last ned Excel",
    data=buf.getvalue(),
    file_name=f"prisgap_{radius_m}m_minN{min_neighbors}.xlsx",
    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
)

# ---------------------------------------------------------------------------
# Kart
# ---------------------------------------------------------------------------

st.subheader("🗺️ Kart – farge = gap_ppm2 (grønn = billig, rød = dyrt)")


def build_map(df_ranked: pd.DataFrame, max_pts: int = 2500) -> folium.Map:
    dfm = df_ranked.dropna(subset=["gap_ppm2", "latitude", "longitude"]).head(max_pts).copy()
    if dfm.empty:
        return folium.Map(location=[59.91, 10.75], zoom_start=12)

    center = [float(dfm["latitude"].mean()), float(dfm["longitude"].mean())]
    m = folium.Map(location=center, zoom_start=13, tiles="CartoDB positron")

    gmin = float(dfm["gap_ppm2"].min())
    gmax = float(dfm["gap_ppm2"].max())
    if math.isclose(gmin, gmax):
        gmin -= 1.0
        gmax += 1.0

    colormap = cm.LinearColormap(
        colors=["#d7191c", "#ffffbf", "#1a9641"],
        vmin=gmin, vmax=gmax
    )
    colormap.caption = "Prisavvik (kr/m²) — grønn = relativt billig"
    colormap.add_to(m)

    for _, r in dfm.iterrows():
        gap = float(r["gap_ppm2"])
        price = r.get("total_price", float("nan"))
        area = r.get("area", float("nan"))
        loc = r.get("location", "")
        fk = r.get("finnkode", "")
        url = r.get("url", "#")
        gap_pct = r.get("gap_pct", float("nan"))

        tooltip = (
            f"<b>{fk}</b><br>"
            f"{loc}<br>"
            f"Gap: {gap:,.0f} kr/m² ({gap_pct:.1f}%)<br>"
            f"Pris: {price:,.0f} kr | Areal: {area:.0f} m²"
        )
        popup_html = f'<a href="{url}" target="_blank">Åpne annonse</a>'

        folium.CircleMarker(
            location=[float(r["latitude"]), float(r["longitude"])],
            radius=5,
            color=colormap(gap),
            fill=True,
            fill_color=colormap(gap),
            fill_opacity=0.85,
            tooltip=tooltip,
            popup=folium.Popup(popup_html, max_width=200),
        ).add_to(m)

    return m


m_folium = build_map(df_valid, max_pts=max_points)
st_folium(m_folium, width="100%", height=650)
