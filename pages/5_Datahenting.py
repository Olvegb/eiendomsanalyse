# Denne filen kan slettes – Datahenting er nå på hjemmesiden (app.py / Overview).
# Slett med: git rm pages/5_Datahenting.py
import streamlit as st
st.set_page_config(page_title="Datahenting (utgått)", page_icon="🔄", layout="wide")
st.warning("⚠️ Denne siden er utgått. Datahenting finner du nå på **🏘️ Overview** i sidepanelet.")
st.stop()
