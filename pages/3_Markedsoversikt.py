"""
Side 3: Markedsoversikt med statistikk og distribusjoner.
"""
from __future__ import annotations

import os
import glob
import math

import numpy as np
import pandas as pd
import streamlit as st

st.set_page_config(page_title="Markedsoversikt", page_icon="📈", layout="wide")
st.title("📈 Markedsoversikt")
st.markdown("Statistikk, distribusjoner og sammenligninger på tvers av datasett.")

# ---------------------------------------------------------------------------
# Datafil-velger (multi-select)
# ---------------------------------------------------------------------------

data_dir = "Data"
json_files = sorted(glob.glob(os.path.join(data_dir, "*.json"))) if os.path.isdir(data_dir) else []
sales_files = [f for f in json_files if "utleie" not in os.path.basename(f).lower()]

if not sales_files:
    st.error("Ingen salgsdatafiler funnet i `Data/`.")
    st.stop()

selected_files = st.multiselect(
    "Velg datasett (kan velge flere for sammenligning)",
    sales_files,
    default=sales_files[:1],
    format_func=os.path.basename,
)

if not selected_files:
    st.info("Velg minst én datafil.")
    st.stop()

# ---------------------------------------------------------------------------
# Last og kombiner data
# ---------------------------------------------------------------------------

from eiendom_analyse_claude.storage.json_store import load_estates


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


dfs = {}
for f in selected_files:
    label = os.path.basename(f).replace(".json", "")
    dfs[label] = load_df(f)

all_df = pd.concat([df.assign(datasett=label) for label, df in dfs.items()], ignore_index=True)

# Legg til avledede kolonner
all_df["pris_per_m2"] = all_df["total_price"] / all_df["area"]
all_df["pris_per_m2_asking"] = all_df["asking_price"] / all_df["area"]

# ---------------------------------------------------------------------------
# Sammendragstabeller
# ---------------------------------------------------------------------------

st.subheader("📊 Sammendragsstatistikk")

summary_rows = []
for label, df in dfs.items():
    ppm2 = (df["total_price"] / df["area"]).replace([np.inf, -np.inf], np.nan).dropna()
    summary_rows.append({
        "Datasett": label,
        "Antall": len(df),
        "Med koordinater": int(df["latitude"].notna().sum()),
        "Median pris": df["total_price"].median(),
        "Snitt pris": df["total_price"].mean(),
        "Median areal (m²)": df["area"].median(),
        "Snitt pris/m²": ppm2.mean(),
        "Median pris/m²": ppm2.median(),
        "Min pris/m²": ppm2.min(),
        "Maks pris/m²": ppm2.max(),
    })

summary_df = pd.DataFrame(summary_rows)
st.dataframe(
    summary_df.style.format({
        "Median pris": "{:,.0f}",
        "Snitt pris": "{:,.0f}",
        "Median areal (m²)": "{:.0f}",
        "Snitt pris/m²": "{:,.0f}",
        "Median pris/m²": "{:,.0f}",
        "Min pris/m²": "{:,.0f}",
        "Maks pris/m²": "{:,.0f}",
    }, na_rep="—"),
    use_container_width=True,
)

# ---------------------------------------------------------------------------
# Distribusjoner
# ---------------------------------------------------------------------------

st.subheader("📉 Prisfordeling")

tab1, tab2, tab3, tab4 = st.tabs(["Totalpris", "Pris per m²", "Areal", "Byggeår"])

with tab1:
    chart_data = {}
    for label, df in dfs.items():
        vals = df["total_price"].dropna()
        vals = vals[(vals > 0) & (vals < 20_000_000)]
        if not vals.empty:
            chart_data[label] = vals.values
    if chart_data:
        max_len = max(len(v) for v in chart_data.values())
        padded = {k: np.pad(v, (0, max_len - len(v)), constant_values=np.nan) for k, v in chart_data.items()}
        st.bar_chart(pd.DataFrame(padded).describe().T[["mean", "50%", "min", "max"]].rename(
            columns={"50%": "median"}
        ))
        st.caption("Statistikk for totalpris")

with tab2:
    ppm2_data = {}
    for label, df in dfs.items():
        vals = (df["total_price"] / df["area"]).replace([np.inf, -np.inf], np.nan).dropna()
        vals = vals[(vals > 0) & (vals < 150_000)]
        if not vals.empty:
            # Lag histogram-bins
            counts, bins = np.histogram(vals, bins=40, range=(0, 100_000))
            bin_labels = [f"{int(b/1000)}k" for b in bins[:-1]]
            ppm2_data[label] = pd.Series(counts, index=bin_labels)

    if ppm2_data:
        st.bar_chart(pd.DataFrame(ppm2_data).fillna(0))
        st.caption("Histogram: antall boliger per pris/m²-intervall")

with tab3:
    area_data = {}
    for label, df in dfs.items():
        vals = df["area"].dropna()
        vals = vals[(vals > 0) & (vals < 500)]
        if not vals.empty:
            counts, bins = np.histogram(vals, bins=30, range=(0, 300))
            bin_labels = [f"{int(b)}" for b in bins[:-1]]
            area_data[label] = pd.Series(counts, index=bin_labels)

    if area_data:
        st.bar_chart(pd.DataFrame(area_data).fillna(0))
        st.caption("Histogram: antall boliger per arealintervall (m²)")

with tab4:
    year_data = {}
    for label, df in dfs.items():
        vals = df["construction_year"].dropna()
        vals = vals[(vals >= 1850) & (vals <= 2025)]
        if not vals.empty:
            counts = vals.astype(int).value_counts().sort_index()
            year_data[label] = counts

    if year_data:
        year_df = pd.DataFrame(year_data).fillna(0)
        st.bar_chart(year_df)
        st.caption("Antall boliger per byggeår")

# ---------------------------------------------------------------------------
# Energimerking
# ---------------------------------------------------------------------------

st.subheader("⚡ Energimerking")

if "energy_label" in all_df.columns:
    energy_counts = {}
    for label, df in dfs.items():
        ec = df["energy_label"].dropna().str[0].value_counts().sort_index()
        energy_counts[label] = ec

    if energy_counts:
        st.bar_chart(pd.DataFrame(energy_counts).fillna(0))
        st.caption("Fordeling av energimerker (A = best, G = dårligst)")

# ---------------------------------------------------------------------------
# Soverom-fordeling
# ---------------------------------------------------------------------------

st.subheader("🛏️ Soveromfordeling")

if "bedrooms" in all_df.columns:
    bed_data = {}
    for label, df in dfs.items():
        bc = df["bedrooms"].dropna()
        bc = bc[(bc >= 0) & (bc <= 10)].astype(int).value_counts().sort_index()
        bc.index = bc.index.map(lambda x: f"{x} soverom")
        bed_data[label] = bc

    if bed_data:
        st.bar_chart(pd.DataFrame(bed_data).fillna(0))

# ---------------------------------------------------------------------------
# Boligtype-fordeling
# ---------------------------------------------------------------------------

if "property_type" in all_df.columns and all_df["property_type"].notna().any():
    st.subheader("🏠 Boligtype-fordeling")
    type_data = {}
    for label, df in dfs.items():
        tc = df["property_type"].dropna().value_counts().head(10)
        type_data[label] = tc

    if type_data:
        st.bar_chart(pd.DataFrame(type_data).fillna(0))

# ---------------------------------------------------------------------------
# Rå data
# ---------------------------------------------------------------------------

with st.expander("🔍 Se rådata"):
    st.dataframe(all_df.head(500), use_container_width=True)
