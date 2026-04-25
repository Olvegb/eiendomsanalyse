"""
Eiendomsanalyse Claude – Hoved-app.

Kjør med:
    streamlit run app.py
"""
from __future__ import annotations

import os
import glob
import streamlit as st

st.set_page_config(
    page_title="Eiendomsanalyse Claude",
    page_icon="🏘️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---------------------------------------------------------------------------
# Hoved-side: Velkommen
# ---------------------------------------------------------------------------

st.title("🏘️ Eiendomsanalyse Claude")
st.markdown(
    """
    **En forbedret eiendomsanalyseplattform for det norske boligmarkedet.**

    Naviger til ønsket analyse i sidepanelet til venstre.
    """
)

# Finn tilgjengelige datafiler
data_dir = "Data"
json_files = glob.glob(os.path.join(data_dir, "*.json")) if os.path.isdir(data_dir) else []

if json_files:
    st.success(f"✅ Fant **{len(json_files)}** datafil(er) i `{data_dir}/`")
    cols = st.columns(min(len(json_files), 4))
    for i, f in enumerate(sorted(json_files)):
        size_kb = os.path.getsize(f) // 1024
        fname = os.path.basename(f)
        with cols[i % 4]:
            st.metric(label=fname, value=f"{size_kb} KB")
else:
    st.warning(
        f"⚠️ Ingen JSON-datafiler funnet i `{data_dir}/`. "
        "Bruk CLI-verktøyene for å hente data fra FINN, "
        "eller last opp eksisterende datafiler."
    )

st.divider()

col1, col2, col3, col4 = st.columns(4)

with col1:
    st.markdown("""
    ### 📊 Prisgap
    Finn relativt underprisede boliger ved å sammenligne
    pris per m² med nærliggende boliger.
    """)

with col2:
    st.markdown("""
    ### 💰 Kontantstrøm
    Beregn estimert netto kontantstrøm, brutto- og nettoavkastning
    og ROI på egenkapital for utleie.
    """)

with col3:
    st.markdown("""
    ### 📈 Markedsoversikt
    Histogrammer og statistikk for pris, areal, energimerking
    og prisutvikling per bydel.
    """)

with col4:
    st.markdown("""
    ### 🔍 Eiendom Detaljer
    Søk opp enkelteiendommer, se alle detaljer og sammenlign
    direkte med nabolaget.
    """)

st.divider()

st.markdown("""
#### Kom i gang – hent data fra FINN

```bash
# Installer avhengigheter
pip install -r requirements.txt

# Hent salgsannonser (Haugesund)
python -m eiendom_analyse_claude.cli.gather \\
    --search-url "https://www.finn.no/realestate/homes/search.html?location=1.20012.20197" \\
    --out Data/finn_Haugesund_estates.json \\
    --type salg

# Hent leieannonser (Haugesund)
python -m eiendom_analyse_claude.cli.gather \\
    --search-url "https://www.finn.no/realestate/lettings/search.html?location=1.20012.20197" \\
    --out Data/finn_Haugesund_utleie.json \\
    --type leie

# Geocode adresser (krever Geoapify API-nøkkel)
export GEOAPIFY_API_KEY="din_nøkkel_her"
python -m eiendom_analyse_claude.cli.geocode \\
    --in Data/finn_Haugesund_estates.json \\
    --out Data/finn_Haugesund_estates.json
```
""")
