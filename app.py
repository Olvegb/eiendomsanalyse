"""
Eiendomsanalyse Claude – navigasjonsrouter.

Kjør med:
    streamlit run app.py
"""
import streamlit as st

st.set_page_config(
    page_title="Eiendomsanalyse",
    page_icon="🏘️",
    layout="wide",
    initial_sidebar_state="expanded",
)

pages = [
    st.Page("pages/0_Overview.py",         title="Overview",          icon="🏘️", default=True),
    st.Page("pages/1_Prisgap.py",          title="Prisgap",           icon="📊"),
    st.Page("pages/2_Kontantstrom.py",     title="Kontantstrøm",      icon="💰"),
    st.Page("pages/3_Markedsoversikt.py",  title="Markedsoversikt",   icon="📈"),
    st.Page("pages/4_Eiendom_Detaljer.py", title="Eiendom Detaljer",  icon="🔍"),
]

pg = st.navigation(pages)
pg.run()
