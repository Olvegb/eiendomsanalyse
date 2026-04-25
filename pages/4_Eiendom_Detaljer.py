"""
Side 4: Søk opp enkelteiendommer og se detaljert informasjon.
"""
from __future__ import annotations

import os
import glob
import math

import folium
import numpy as np
import pandas as pd
import streamlit as st
from streamlit_folium import st_folium

from eiendom_analyse_claude.storage.json_store import load_estates, load_rentals
from eiendom_analyse_claude.analysis.cashflow import avg_rental_per_m2

try:
    from eiendom_analyse_claude.analysis.price_gap import compute_price_gaps
    _HAS_SKLEARN = True
except ImportError:
    _HAS_SKLEARN = False

st.set_page_config(page_title="Eiendom Detaljer", page_icon="🔍", layout="wide")
st.title("🔍 Eiendom Detaljer")
st.markdown("Søk opp enkeltboliger og se full informasjon, nabosammenligning og nærliggende utleieobjekter.")

# ---------------------------------------------------------------------------
# Datafil-velgere
# ---------------------------------------------------------------------------

data_dir = "Data"
json_files = sorted(glob.glob(os.path.join(data_dir, "*.json"))) if os.path.isdir(data_dir) else []
sales_files = [f for f in json_files if "utleie" not in os.path.basename(f).lower()]
rental_files = [f for f in json_files if "utleie" in os.path.basename(f).lower()]

if not sales_files:
    st.error("Ingen salgsdatafiler funnet i `Data/`.")
    st.stop()

fc1, fc2 = st.columns(2)
with fc1:
    selected_file = st.selectbox("Salgsdatafil", sales_files, format_func=os.path.basename)
with fc2:
    # Prøv å forhåndsvelge utleiefil med samme bynavn
    base = os.path.basename(selected_file).lower()
    city_hint = next(
        (w for w in base.replace(".json", "").split("_") if len(w) > 3 and w not in ("finn", "estates", "estate")),
        None,
    )
    auto_rental = next(
        (f for f in rental_files if city_hint and city_hint in os.path.basename(f).lower()),
        rental_files[0] if rental_files else None,
    )
    if rental_files:
        rental_idx = rental_files.index(auto_rental) if auto_rental in rental_files else 0
        rental_file = st.selectbox(
            "Utleiefil (for leiedata)",
            rental_files,
            index=rental_idx,
            format_func=os.path.basename,
        )
    else:
        st.info("Ingen utleiefiler i `Data/`")
        rental_file = None

# Radius-valg
nb_radius = st.slider("Radius for nabovisning (meter)", 200, 2000, 500, 100)


# ---------------------------------------------------------------------------
# Last data
# ---------------------------------------------------------------------------

@st.cache_data
def _load_sales_df(path: str) -> pd.DataFrame:
    estates = load_estates(path)
    rows = []
    for est in estates.values():
        d = est.to_dict()
        if isinstance(d.get("neighbors"), list):
            d["neighbors"] = ",".join(d["neighbors"])
        rows.append(d)
    return pd.DataFrame(rows)


@st.cache_data
def _load_rental_df(path: str) -> pd.DataFrame:
    rentals = load_rentals(path)
    rows = [r.to_dict() for r in rentals.values()]
    df = pd.DataFrame(rows)
    if not df.empty and "monthly_rent" in df.columns and "primary_area" in df.columns:
        df["leie_per_m2"] = df["monthly_rent"] / df["primary_area"]
        df["leie_per_m2"] = df["leie_per_m2"].replace([np.inf, -np.inf], np.nan)
    return df


df = _load_sales_df(selected_file)
df["pris_per_m2"] = df["total_price"] / df["area"]

df_rentals = _load_rental_df(rental_file) if rental_file else pd.DataFrame()

# ---------------------------------------------------------------------------
# Søk
# ---------------------------------------------------------------------------

st.subheader("🔎 Søk")
search_col, filter_col = st.columns([3, 1])

with search_col:
    query = st.text_input(
        "Søk på finnkode, adresse eller sted",
        placeholder="f.eks. 123456789, Haugesund, ...",
    )

with filter_col:
    max_results = st.selectbox("Maks treff", [10, 25, 50, 100], index=1)

if query:
    q = query.lower().strip()
    mask = (
        df["finnkode"].astype(str).str.lower().str.contains(q, na=False)
        | df["location"].astype(str).str.lower().str.contains(q, na=False)
        | df.get("title", pd.Series(dtype=str)).astype(str).str.lower().str.contains(q, na=False)
    )
    results = df[mask].head(max_results)
else:
    results = df.sort_values("pris_per_m2", na_position="last").head(max_results)

if results.empty:
    st.warning("Ingen treff.")
    st.stop()

# ---------------------------------------------------------------------------
# Velg eiendom
# ---------------------------------------------------------------------------

def _label(row):
    loc = row.get("location", "") or ""
    fk = row.get("finnkode", "")
    price = row.get("total_price", float("nan"))
    area = row.get("area", float("nan"))
    try:
        price_str = f"{float(price):,.0f} kr"
    except Exception:
        price_str = "—"
    try:
        area_str = f"{float(area):.0f} m²"
    except Exception:
        area_str = "—"
    return f"{fk} | {loc} | {price_str} | {area_str}"


labels = [_label(row) for _, row in results.iterrows()]
selected_label = st.selectbox("Velg eiendom", labels)
selected_idx = labels.index(selected_label)
selected_row = results.iloc[selected_idx]

# ---------------------------------------------------------------------------
# Koordinatsjekk
# ---------------------------------------------------------------------------

lat = selected_row.get("latitude", float("nan"))
lon = selected_row.get("longitude", float("nan"))
try:
    lat_f = float(lat)
    lon_f = float(lon)
    has_coords = not math.isnan(lat_f) and not math.isnan(lon_f)
except Exception:
    has_coords = False

# ---------------------------------------------------------------------------
# Hjelpefunksjon
# ---------------------------------------------------------------------------

def fmt(val, fmt_str="{:,.0f}", suffix=""):
    try:
        v = float(val)
        if math.isnan(v):
            return "—"
        return fmt_str.format(v) + suffix
    except Exception:
        return str(val) if val else "—"


def haversine_m(lat1, lon1, lat2, lon2) -> float:
    """Avstand i meter mellom to koordinater."""
    R = 6_371_000.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2) ** 2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2) ** 2
    return R * 2 * math.asin(math.sqrt(a))


# ---------------------------------------------------------------------------
# Finn nabo-utleieobjekter
# ---------------------------------------------------------------------------

nearby_rentals: pd.DataFrame = pd.DataFrame()
if has_coords and not df_rentals.empty:
    lat_col = "latitude" if "latitude" in df_rentals.columns else None
    lon_col = "longitude" if "longitude" in df_rentals.columns else None
    if lat_col and lon_col:
        df_r_geo = df_rentals[df_rentals[lat_col].notna() & df_rentals[lon_col].notna()].copy()
        if not df_r_geo.empty:
            df_r_geo["avstand_m"] = df_r_geo.apply(
                lambda r: haversine_m(lat_f, lon_f, float(r[lat_col]), float(r[lon_col])),
                axis=1,
            )
            nearby_rentals = (
                df_r_geo[df_r_geo["avstand_m"] <= nb_radius]
                .sort_values("avstand_m")
                .reset_index(drop=True)
            )

# ---------------------------------------------------------------------------
# Layout: info + kart
# ---------------------------------------------------------------------------

st.divider()
fk = selected_row.get("finnkode", "")
url = selected_row.get("url", "#")

col_info, col_map = st.columns([1, 2])

with col_info:
    st.subheader(f"🏠 {selected_row.get('title', fk) or fk}")
    if url and url != "#":
        st.markdown(f"[🔗 Åpne annonse på FINN.no]({url})")

    st.markdown("#### 📍 Adresse og type")
    st.markdown(f"**Adresse:** {selected_row.get('location', '—') or '—'}")
    st.markdown(f"**Boligtype:** {selected_row.get('property_type', '—') or '—'}")
    st.markdown(f"**Energimerke:** {selected_row.get('energy_label', '—') or '—'}")
    st.markdown(f"**Etasje:** {fmt(selected_row.get('floor'), '{:.0f}')}")
    st.markdown(f"**Byggeår:** {fmt(selected_row.get('construction_year'), '{:.0f}')}")

    st.markdown("#### 📐 Areal")
    st.markdown(f"**Bruksareal:** {fmt(selected_row.get('area'), '{:.0f}', ' m²')}")
    st.markdown(f"**Soverom:** {fmt(selected_row.get('bedrooms'), '{:.0f}')}")
    st.markdown(f"**Rom:** {fmt(selected_row.get('rooms'), '{:.0f}')}")

    st.markdown("#### 💰 Priser")
    st.markdown(f"**Totalpris:** {fmt(selected_row.get('total_price'))} kr")
    st.markdown(f"**Prisantydning:** {fmt(selected_row.get('asking_price'))} kr")
    st.markdown(f"**Fellesgjeld:** {fmt(selected_row.get('joint_debt'))} kr")
    st.markdown(f"**Felleskost/mnd:** {fmt(selected_row.get('common_monthly_cost'))} kr")
    st.markdown(f"**Kommunale avgifter/år:** {fmt(selected_row.get('municipality_cost_year'))} kr")
    st.markdown(f"**Pris/m²:** {fmt(selected_row.get('pris_per_m2'))} kr/m²")

    # Leieestimat-boks
    if not nearby_rentals.empty and "leie_per_m2" in nearby_rentals.columns:
        valid_lpm2 = nearby_rentals["leie_per_m2"].dropna()
        if not valid_lpm2.empty:
            avg_lpm2 = valid_lpm2.mean()
            area_val = selected_row.get("area", float("nan"))
            try:
                est_rent = avg_lpm2 * float(area_val)
            except Exception:
                est_rent = float("nan")

            st.markdown("#### 🏷️ Leieestimat (nabodata)")
            st.info(
                f"Snitt leie/m²/mnd fra **{len(valid_lpm2)}** nærliggende leieobjekter: "
                f"**{avg_lpm2:.0f} kr/m²**\n\n"
                + (f"Estimert månedlig leie for **{float(area_val):.0f} m²**: **{est_rent:,.0f} kr/mnd**"
                   if not math.isnan(est_rent) else "")
            )


with col_map:
    if has_coords:
        m = folium.Map(location=[lat_f, lon_f], zoom_start=14, tiles="CartoDB positron")

        # Rød markør – valgt salgsobjekt
        folium.Marker(
            location=[lat_f, lon_f],
            tooltip=f"<b>{fk}</b> (valgt)<br>{selected_row.get('location', '')}",
            icon=folium.Icon(color="red", icon="home", prefix="fa"),
        ).add_to(m)

        # Blå sirkler – nabo-salgsobjekter
        df_geo = df[df["latitude"].notna() & df["longitude"].notna()].copy()
        for _, nb in df_geo.iterrows():
            if nb["finnkode"] == fk:
                continue
            nb_lat = float(nb["latitude"])
            nb_lon = float(nb["longitude"])
            dist = haversine_m(lat_f, lon_f, nb_lat, nb_lon)
            if dist <= nb_radius:
                nb_ppm2 = nb.get("pris_per_m2", float("nan"))
                folium.CircleMarker(
                    location=[nb_lat, nb_lon],
                    radius=5,
                    color="#1565C0",
                    fill=True,
                    fill_color="#1565C0",
                    fill_opacity=0.65,
                    tooltip=(
                        f"<b>SALG</b> – {nb.get('finnkode', '')}<br>"
                        f"{nb.get('location', '')}<br>"
                        f"{fmt(nb.get('area'), '{:.0f}', ' m²')} | "
                        f"{fmt(nb_ppm2)} kr/m²"
                    ),
                ).add_to(m)

        # Grønne sirkler – nabo-utleieobjekter
        if not nearby_rentals.empty:
            for _, r in nearby_rentals.iterrows():
                r_lat = float(r.get("latitude", float("nan")))
                r_lon = float(r.get("longitude", float("nan")))
                if math.isnan(r_lat) or math.isnan(r_lon):
                    continue
                lpm2 = r.get("leie_per_m2", float("nan"))
                rent = r.get("monthly_rent", float("nan"))
                area_r = r.get("primary_area", float("nan"))
                dist_r = r.get("avstand_m", float("nan"))
                r_url = r.get("url", "#")
                popup_html = f'<a href="{r_url}" target="_blank">Åpne leieannonse</a>'
                folium.CircleMarker(
                    location=[r_lat, r_lon],
                    radius=6,
                    color="#2E7D32",
                    fill=True,
                    fill_color="#43A047",
                    fill_opacity=0.8,
                    tooltip=(
                        f"<b>LEIE</b> – {r.get('finnkode', '')}<br>"
                        f"{r.get('location', '') or r.get('title', '')}<br>"
                        f"Leie: {fmt(rent)} kr/mnd | "
                        f"{fmt(area_r, '{:.0f}', ' m²')} | "
                        f"{fmt(lpm2)} kr/m²<br>"
                        f"Avstand: {fmt(dist_r, '{:.0f}', ' m')}"
                    ),
                    popup=folium.Popup(popup_html, max_width=200),
                ).add_to(m)

        # Radius-sirkel
        folium.Circle(
            location=[lat_f, lon_f],
            radius=nb_radius,
            color="#888",
            fill=False,
            dash_array="5",
            tooltip=f"{nb_radius} m radius",
        ).add_to(m)

        # Tegnforklaring (manuell)
        legend_html = """
        <div style="position:fixed;bottom:30px;left:30px;z-index:1000;background:white;
                    padding:10px 14px;border-radius:8px;border:1px solid #ccc;font-size:13px;">
            <b>Tegnforklaring</b><br>
            <span style="color:#c62828;">&#9632;</span> Valgt salgsobjekt<br>
            <span style="color:#1565C0;">&#11044;</span> Nabo-salgsobjekter<br>
            <span style="color:#2E7D32;">&#11044;</span> Nærliggende leieobjekter
        </div>
        """
        m.get_root().html.add_child(folium.Element(legend_html))

        st_folium(m, width="100%", height=500)
    else:
        st.info("Ingen kartkoordinater tilgjengelig for denne eiendommen.")
        st.markdown("Kjør geocoding for å legge til koordinater.")

# ---------------------------------------------------------------------------
# Nabosammenligning – salgspriser
# ---------------------------------------------------------------------------

st.subheader("👥 Nabosalgsobjekter innen radius")

if has_coords:
    df_geo = df[
        df["latitude"].notna() & df["longitude"].notna() &
        df["total_price"].notna() & df["area"].notna()
    ].copy()
    df_geo = df_geo[df_geo["area"] > 0].copy()
    df_geo["pris_per_m2"] = df_geo["total_price"] / df_geo["area"]
    df_geo["avstand_m"] = df_geo.apply(
        lambda r: haversine_m(lat_f, lon_f, float(r["latitude"]), float(r["longitude"])),
        axis=1,
    )
    sale_neighbors = df_geo[
        (df_geo["avstand_m"] <= nb_radius) & (df_geo["finnkode"] != fk)
    ].sort_values("avstand_m").reset_index(drop=True)

    if not sale_neighbors.empty:
        avg_nb_ppm2 = sale_neighbors["pris_per_m2"].mean()
        own_ppm2 = selected_row.get("pris_per_m2", float("nan"))
        try:
            own_ppm2_f = float(own_ppm2)
            gap = avg_nb_ppm2 - own_ppm2_f
            gap_pct = gap / avg_nb_ppm2 * 100 if avg_nb_ppm2 > 0 else float("nan")
        except Exception:
            gap = float("nan")
            gap_pct = float("nan")

        gm1, gm2, gm3 = st.columns(3)
        with gm1:
            st.metric("Eget pris/m²", fmt(own_ppm2) + " kr")
        with gm2:
            st.metric(f"Nabosnitt pris/m² ({len(sale_neighbors)} nabo(er))", f"{avg_nb_ppm2:,.0f} kr")
        with gm3:
            st.metric(
                "Prisavvik (gap)",
                fmt(gap) + " kr/m²" if not math.isnan(gap) else "—",
                delta=f"{gap_pct:.1f}%" if not math.isnan(gap_pct) else None,
            )

        sale_disp_cols = [
            c for c in ["finnkode", "location", "property_type", "area", "bedrooms",
                        "construction_year", "energy_label", "total_price",
                        "pris_per_m2", "avstand_m", "url"]
            if c in sale_neighbors.columns
        ]
        st.dataframe(
            sale_neighbors[sale_disp_cols].style.format(
                {
                    "area": "{:.0f}",
                    "total_price": "{:,.0f}",
                    "pris_per_m2": "{:,.0f}",
                    "avstand_m": "{:.0f}",
                    "bedrooms": "{:.0f}",
                    "construction_year": "{:.0f}",
                },
                na_rep="—",
            ),
            use_container_width=True,
        )
    else:
        st.info(f"Ingen salgsobjekter med koordinater innen {nb_radius} m.")
else:
    st.info("Koordinater mangler – kan ikke beregne naboavstand.")

# ---------------------------------------------------------------------------
# Nærliggende utleieobjekter
# ---------------------------------------------------------------------------

st.subheader("🏷️ Nærliggende utleieobjekter innen radius")

if not has_coords:
    st.info("Koordinater mangler – kan ikke beregne avstand til utleieobjekter.")
elif df_rentals.empty:
    st.info("Ingen utleiefil valgt eller utleiefilen er tom.")
elif nearby_rentals.empty:
    st.info(f"Ingen utleieobjekter med koordinater funnet innen {nb_radius} m.")
else:
    valid_lpm2 = nearby_rentals["leie_per_m2"].dropna() if "leie_per_m2" in nearby_rentals.columns else pd.Series()

    rm1, rm2, rm3, rm4 = st.columns(4)
    with rm1:
        st.metric("Leieobjekter funnet", len(nearby_rentals))
    with rm2:
        if not valid_lpm2.empty:
            st.metric("Snitt leie/m²/mnd", f"{valid_lpm2.mean():.0f} kr")
        else:
            st.metric("Snitt leie/m²/mnd", "—")
    with rm3:
        if not valid_lpm2.empty:
            st.metric("Min leie/m²/mnd", f"{valid_lpm2.min():.0f} kr")
        else:
            st.metric("Min leie/m²/mnd", "—")
    with rm4:
        if not valid_lpm2.empty:
            st.metric("Maks leie/m²/mnd", f"{valid_lpm2.max():.0f} kr")
        else:
            st.metric("Maks leie/m²/mnd", "—")

    rental_disp_cols = [
        c for c in [
            "finnkode", "title", "location", "property_type",
            "primary_area", "bedrooms", "floor",
            "monthly_rent", "leie_per_m2", "deposit",
            "lease_period", "avstand_m", "url",
        ]
        if c in nearby_rentals.columns
    ]

    rename_map = {
        "finnkode": "Finnkode",
        "title": "Tittel",
        "location": "Adresse",
        "property_type": "Type",
        "primary_area": "Areal (m²)",
        "bedrooms": "Soverom",
        "floor": "Etasje",
        "monthly_rent": "Leie/mnd (kr)",
        "leie_per_m2": "Leie/m²/mnd (kr)",
        "deposit": "Depositum (kr)",
        "lease_period": "Leieperiode",
        "avstand_m": "Avstand (m)",
        "url": "URL",
    }

    display_df = (
        nearby_rentals[rental_disp_cols]
        .rename(columns=rename_map)
    )

    fmt_cols = {v: "{:,.0f}" for v in ["Areal (m²)", "Leie/mnd (kr)", "Depositum (kr)"]}
    fmt_cols["Leie/m²/mnd (kr)"] = "{:.0f}"
    fmt_cols["Avstand (m)"] = "{:.0f}"
    fmt_cols["Soverom"] = "{:.0f}"
    fmt_cols["Etasje"] = "{:.0f}"

    st.dataframe(
        display_df.style.format(
            {k: v for k, v in fmt_cols.items() if k in display_df.columns},
            na_rep="—",
        ).background_gradient(
            subset=["Leie/m²/mnd (kr)"] if "Leie/m²/mnd (kr)" in display_df.columns else [],
            cmap="YlGn",
        ),
        use_container_width=True,
        height=min(400, 50 + len(nearby_rentals) * 38),
    )

    # Distribusjon av leiepriser
    if not valid_lpm2.empty and len(valid_lpm2) >= 3:
        st.markdown("**Fordeling av leie/m²/mnd blant nærliggende objekter**")
        bins = pd.cut(valid_lpm2, bins=min(10, len(valid_lpm2)), precision=0)
        hist_df = bins.value_counts().sort_index().rename_axis("Leie/m²/mnd").reset_index(name="Antall")
        hist_df["Leie/m²/mnd"] = hist_df["Leie/m²/mnd"].astype(str)
        st.bar_chart(hist_df.set_index("Leie/m²/mnd")["Antall"])
