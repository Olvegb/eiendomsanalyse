"""
Side 2: Kontantstrøm- og avkastningsanalyse for utleieinvestering.
"""
from __future__ import annotations

import io
import os
import glob
import math

import pandas as pd
import streamlit as st

from eiendom_analyse_claude.storage.json_store import load_estates, load_rentals
from eiendom_analyse_claude.analysis.cashflow import (
    CashflowParams, run_cashflow_analysis, CashflowResult, avg_rental_per_m2,
)

st.set_page_config(page_title="Kontantstrøm", page_icon="💰", layout="wide")
st.title("💰 Kontantstrøm- og avkastningsanalyse")
st.markdown(
    "Estimert **netto kontantstrøm**, **brutto-/nettoavkastning** og "
    "**ROI på egenkapital** for utleie, basert på nærliggende leieannonser."
)

# ---------------------------------------------------------------------------
# Datafil-velgere
# ---------------------------------------------------------------------------

data_dir = "Data"
json_files = sorted(glob.glob(os.path.join(data_dir, "*.json"))) if os.path.isdir(data_dir) else []
sales_files = [f for f in json_files if "utleie" not in os.path.basename(f).lower()]
rental_files = [f for f in json_files if "utleie" in os.path.basename(f).lower()]

TEMPLATE_PATH = os.path.join(data_dir, "Excel_template", "Boligkalkulator1.xlsx")

if not sales_files:
    st.error("Ingen salgsdatafiler funnet i `Data/`.")
    st.stop()

c1, c2 = st.columns(2)
with c1:
    sales_file = st.selectbox("Salgsfil", sales_files, format_func=os.path.basename)
with c2:
    if rental_files:
        rental_file = st.selectbox("Leiefil", rental_files, format_func=os.path.basename)
    else:
        st.warning("Ingen leiefiler funnet. Bruker standard leie/m².")
        rental_file = None

# ---------------------------------------------------------------------------
# Parametere
# ---------------------------------------------------------------------------

st.subheader("⚙️ Investerings- og kostnadsparametere")

with st.expander("💵 Finansiering", expanded=True):
    fp1, fp2, fp3 = st.columns(3)
    with fp1:
        equity = st.number_input("Egenkapital (NOK)", min_value=0, max_value=10_000_000,
                                 value=500_000, step=50_000)
    with fp2:
        interest_rate = st.slider("Rente (%)", 1.0, 12.0, 5.5, 0.1) / 100
    with fp3:
        loan_years = st.slider("Nedbetalingstid (år)", 5, 30, 25, 1)

    interest_only = st.checkbox("Kun renter (ingen avdrag)")

with st.expander("🏠 Driftskostnader", expanded=True):
    cp1, cp2, cp3 = st.columns(3)
    with cp1:
        insurance = st.number_input("Forsikring (NOK/år)", 0, 50_000, 3_000, 500)
        tax = st.number_input("Eiendomsskatt (NOK/år)", 0, 100_000, 0, 500)
    with cp2:
        maintenance_pct = st.slider("Vedlikehold (% av brutto leie/år)", 0.0, 20.0, 5.0, 0.5) / 100
        vacancy_months = st.slider("Tomgangsmåneder/år", 0.0, 6.0, 1.0, 0.5)
    with cp3:
        default_rent_pm2 = st.number_input(
            "Fallback leie (kr/m²/mnd) – brukes uten nabodata",
            50, 500, 150, 10
        )
        radius_m = st.slider("Radius for leieestimering (meter)", 200, 3000, 1000, 100)

with st.expander("⚡ Strøm", expanded=False):
    ep1, ep2, ep3 = st.columns(3)
    with ep1:
        electricity_price = st.slider("Strømpris (kr/kWh)", 0.3, 3.0, 0.85, 0.05)
    with ep2:
        kwh_per_m2 = st.slider("Forbruk (kWh/m²/år)", 50, 300, 150, 10)
    with ep3:
        tenant_pays = st.checkbox("Leietaker betaler strøm", value=True)

p = CashflowParams(
    equity=float(equity),
    interest_rate=interest_rate,
    loan_years=loan_years,
    interest_only=interest_only,
    insurance=float(insurance),
    tax=float(tax),
    maintenance_pct_rent=maintenance_pct,
    vacancy_months=vacancy_months,
    electricity_price=electricity_price,
    kwh_per_m2=float(kwh_per_m2),
    tenant_pays_electricity=tenant_pays,
    default_rent_per_m2=float(default_rent_pm2),
)

# ---------------------------------------------------------------------------
# Kjør analyse
# ---------------------------------------------------------------------------

@st.cache_data
def _load_sales(path):
    return load_estates(path)

@st.cache_data
def _load_rentals_cached(path):
    return load_rentals(path)


with st.spinner("Beregner kontantstrøm..."):
    sales = _load_sales(sales_file)
    rentals = _load_rentals_cached(rental_file) if rental_file else {}
    results: list[CashflowResult] = run_cashflow_analysis(sales, rentals, p, radius_m=radius_m)

if not results:
    st.error("Ingen resultater. Sjekk at datafiler er gyldige og inneholder areal/pris.")
    st.stop()

# Lag oppslagsdict: finnkode -> estimert månedlig leie
rent_lookup: dict[str, float] = {r.finnkode: r.estimated_rent_monthly for r in results}

# ---------------------------------------------------------------------------
# Konverter til DataFrame
# ---------------------------------------------------------------------------

rows = []
for r in results:
    estate = sales.get(r.finnkode)
    loc = estate.location if estate else ""
    rows.append({
        "finnkode": r.finnkode,
        "adresse": loc or "",
        "kjøpspris": r.sales_price,
        "areal (m²)": r.area,
        "est. leie/mnd": r.estimated_rent_monthly,
        "energimerke": r.energy_label,
        "brutto leie/år": r.gross_rent_year,
        "renter/år": r.interest_year,
        "avdrag/år": r.principal_year,
        "felleskost/år": r.common_cost_year,
        "kommunale avg./år": r.kommunale_avgifter_year,
        "forsikring/år": r.insurance_year,
        "vedlikehold/år": r.maintenance_year,
        "strøm/år": r.electricity_year,
        "netto kontantstrøm/år": r.netto_cashflow_year,
        "brutto avkastning (%)": r.gross_yield_pct,
        "netto avkastning (%)": r.net_yield_pct,
        "ROI egenkapital (%)": r.roi_pct,
        "url": sales[r.finnkode].url if r.finnkode in sales else "#",
    })

df = pd.DataFrame(rows).sort_values("netto kontantstrøm/år", ascending=False)

# ---------------------------------------------------------------------------
# Nøkkeltall
# ---------------------------------------------------------------------------

m1, m2, m3, m4 = st.columns(4)
positive = (df["netto kontantstrøm/år"] > 0).sum()
with m1:
    st.metric("Analyserte boliger", len(df))
with m2:
    st.metric("Positiv kontantstrøm", positive, delta=f"{positive/len(df)*100:.0f}%")
with m3:
    best = df["netto kontantstrøm/år"].iloc[0]
    st.metric("Beste kontantstrøm/år", f"{best:,.0f} kr")
with m4:
    best_roi = df["ROI egenkapital (%)"].max()
    st.metric("Beste ROI", f"{best_roi:.1f} %")

# ---------------------------------------------------------------------------
# Tabell
# ---------------------------------------------------------------------------

st.subheader("📋 Resultater")

def color_cashflow(val):
    try:
        if float(val) > 0:
            return "color: green"
        elif float(val) < 0:
            return "color: red"
    except Exception:
        pass
    return ""

fmt_cols = {
    "kjøpspris": "{:,.0f}",
    "areal (m²)": "{:.0f}",
    "est. leie/mnd": "{:,.0f}",
    "brutto leie/år": "{:,.0f}",
    "renter/år": "{:,.0f}",
    "avdrag/år": "{:,.0f}",
    "felleskost/år": "{:,.0f}",
    "kommunale avg./år": "{:,.0f}",
    "forsikring/år": "{:,.0f}",
    "vedlikehold/år": "{:,.0f}",
    "strøm/år": "{:,.0f}",
    "netto kontantstrøm/år": "{:,.0f}",
    "brutto avkastning (%)": "{:.2f}",
    "netto avkastning (%)": "{:.2f}",
    "ROI egenkapital (%)": "{:.2f}",
}

display_cols = [c for c in fmt_cols.keys() if c in df.columns]
display_cols = ["finnkode", "adresse"] + display_cols + ["energimerke", "url"]
display_df = df[[c for c in display_cols if c in df.columns]].head(300)

st.dataframe(
    display_df.style
    .format(fmt_cols, na_rep="—")
    .map(color_cashflow, subset=["netto kontantstrøm/år"]),
    use_container_width=True,
    height=500,
)

# ---------------------------------------------------------------------------
# Kostnadsfordeling – topp bolig
# ---------------------------------------------------------------------------

st.subheader("🥧 Kostnadsfordeling – beste objekt")

if not df.empty:
    best_row = df.iloc[0]
    cost_data = {
        "Renter": best_row["renter/år"],
        "Avdrag": best_row["avdrag/år"],
        "Felleskost": best_row["felleskost/år"],
        "Kommunale avg.": best_row["kommunale avg./år"],
        "Forsikring": best_row["forsikring/år"],
        "Vedlikehold": best_row["vedlikehold/år"],
        "Strøm": best_row["strøm/år"],
    }
    cost_df = pd.DataFrame.from_dict(cost_data, orient="index", columns=["NOK/år"])
    cost_df = cost_df[cost_df["NOK/år"] > 0]

    col_chart, col_info = st.columns([2, 1])
    with col_chart:
        st.bar_chart(cost_df)
    with col_info:
        st.markdown(f"""
        **Finnkode:** {best_row['finnkode']}
        **Kjøpspris:** {best_row['kjøpspris']:,.0f} kr
        **Areal:** {best_row['areal (m²)']:.0f} m²
        **Est. leie/mnd:** {best_row['est. leie/mnd']:,.0f} kr
        ---
        **Brutto leie/år:** {best_row['brutto leie/år']:,.0f} kr
        **Netto kontantstrøm:** {best_row['netto kontantstrøm/år']:,.0f} kr/år
        **Brutto yield:** {best_row['brutto avkastning (%)']:.2f} %
        **Netto yield:** {best_row['netto avkastning (%)']:.2f} %
        **ROI:** {best_row['ROI egenkapital (%)']:.2f} %
        """)

# ---------------------------------------------------------------------------
# Eksport – samlet tabell
# ---------------------------------------------------------------------------

st.subheader("📥 Eksporter tabell til Excel")
buf = io.BytesIO()
with pd.ExcelWriter(buf, engine="openpyxl") as writer:
    df.to_excel(writer, index=False, sheet_name="kontantstrøm")
st.download_button(
    "Last ned tabell (Excel)",
    data=buf.getvalue(),
    file_name="kontantstrom_analyse.xlsx",
    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
)

# ---------------------------------------------------------------------------
# Boligkalkulator-eksport (fylt inn Excel-template)
# ---------------------------------------------------------------------------

st.divider()
st.subheader("📊 Last ned Boligkalkulator for én eiendom")
st.markdown(
    "Velg en eiendom nedenfor og last ned en **ferdig utfylt Boligkalkulator** "
    "basert på templatefilen og dine analyseparametere."
)

if not os.path.exists(TEMPLATE_PATH):
    st.error(
        f"Templatefil ikke funnet: `{TEMPLATE_PATH}`. "
        "Sjekk at `Data/Excel_template/Boligkalkulator1.xlsx` finnes."
    )
else:
    # Bygg valgmuligheter: "finnkode | adresse | pris | leie_est"
    def _row_label(row: pd.Series) -> str:
        fk  = row.get("finnkode", "")
        adr = (row.get("adresse", "") or "")[:40]
        pris = row.get("kjøpspris", float("nan"))
        leie = row.get("est. leie/mnd", float("nan"))
        try:
            pris_str = f"{float(pris):,.0f} kr"
        except Exception:
            pris_str = "—"
        try:
            leie_str = f"{float(leie):,.0f} kr/mnd"
        except Exception:
            leie_str = "—"
        return f"{fk}  |  {adr}  |  {pris_str}  |  leie {leie_str}"

    labels = [_row_label(row) for _, row in df.iterrows()]
    fk_list = df["finnkode"].tolist()

    xc1, xc2 = st.columns([3, 1])
    with xc1:
        selected_label = st.selectbox(
            "Velg eiendom",
            labels,
            key="excel_property_select",
        )
    with xc2:
        tv_net = st.number_input(
            "TV og nett (kr/mnd)",
            min_value=0, max_value=5_000,
            value=800, step=50,
            key="tv_net_input",
        )

    selected_idx = labels.index(selected_label)
    selected_fk  = fk_list[selected_idx]
    selected_row = df.iloc[selected_idx]
    estate = sales.get(selected_fk)

    if estate is None:
        st.warning("Kunne ikke hente eiendomsdata for valgt finnkode.")
    else:
        # Vis en liten oppsummering
        sum_col1, sum_col2, sum_col3, sum_col4 = st.columns(4)
        with sum_col1:
            st.metric("Kjøpspris", f"{selected_row['kjøpspris']:,.0f} kr")
        with sum_col2:
            st.metric("Areal", f"{selected_row['areal (m²)']:.0f} m²")
        with sum_col3:
            st.metric("Est. leie/mnd", f"{selected_row['est. leie/mnd']:,.0f} kr")
        with sum_col4:
            st.metric("Netto KS/år", f"{selected_row['netto kontantstrøm/år']:,.0f} kr")

        # Generer Excel
        from eiendom_analyse_claude.analysis.excel_export import fill_boligkalkulator

        try:
            excel_bytes = fill_boligkalkulator(
                estate=estate,
                rent_monthly=float(selected_row["est. leie/mnd"]),
                params=p,
                template_path=TEMPLATE_PATH,
                tv_net_monthly=float(tv_net),
            )

            safe_addr = (
                (estate.location or estate.finnkode)
                .replace("/", "-")
                .replace("\\", "-")
                .replace(" ", "_")
            )[:40]

            st.download_button(
                label="📥 Last ned Boligkalkulator.xlsx",
                data=excel_bytes,
                file_name=f"Boligkalkulator_{safe_addr}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                type="primary",
            )

            # Vis hva som er fylt inn
            with st.expander("ℹ️ Hva ble fylt inn i templaten?"):
                reg = estate.registration_charge if not math.isnan(estate.registration_charge) else 0
                area_val = estate.area if not math.isnan(estate.area) else 0
                elec_m = (
                    0 if tenant_pays
                    else round(kwh_per_m2 * area_val * electricity_price / 12, 0)
                )
                common_m = estate.common_monthly_cost if not math.isnan(estate.common_monthly_cost) else 0

                kom_avg = estate.municipality_cost_year if not math.isnan(estate.municipality_cost_year) else 0
                fill_table = pd.DataFrame([
                    ("Adresse / tittel",           estate.location or estate.finnkode),
                    ("Kjøpesum (prisantydning)",    f"{estate.asking_price:,.0f} kr" if not math.isnan(estate.asking_price) else "—"),
                    ("Transaksjonskostnader",        f"{reg:,.0f} kr"),
                    ("Egenkapital",                  f"{equity:,.0f} kr"),
                    ("Rentenivå",                    f"{interest_rate*100:.2f} %"),
                    ("Månedlig leie (estimert)",     f"{selected_row['est. leie/mnd']:,.0f} kr"),
                    ("Felleskost / mnd",             f"{common_m:,.0f} kr"),
                    ("Kommunale avgifter / år",      f"{kom_avg:,.0f} kr"),
                    ("Forsikring (mnd)",             f"{insurance/12:,.0f} kr"),
                    ("Vedlikeholdskostnad",          f"{maintenance_pct*100:.1f} % av leie"),
                    ("TV og nett / mnd",             f"{tv_net:,.0f} kr"),
                    ("Strøm / mnd",                  f"{elec_m:,.0f} kr" + (" (leietaker betaler)" if tenant_pays else "")),
                    ("Energimerke",                  estate.energy_label or "—"),
                ], columns=["Felt", "Verdi"])

                st.dataframe(fill_table, use_container_width=True, hide_index=True)

        except Exception as e:
            st.error(f"Kunne ikke generere Excel: {e}")
