"""
Side 5: Datahenting – start skraping av FINN direkte fra nettleseren.
"""
from __future__ import annotations

import json
import math
import os
import signal
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

import streamlit as st

st.set_page_config(page_title="Datahenting", page_icon="🔄", layout="wide")
st.title("🔄 Datahenting fra FINN")
st.markdown(
    "Start og følg med på innhenting av boligannonser direkte herfra. "
    "Skrapingen kjører i bakgrunnen – du kan navigere fritt i appen mens den jobber."
)

# ---------------------------------------------------------------------------
# Konfig – samme som i run_*.py
# ---------------------------------------------------------------------------

PROJECT_ROOT = Path(__file__).parent.parent
DATA_DIR = PROJECT_ROOT / "Data"
LOG_FILE  = DATA_DIR / "scrape_log.txt"

JOBS = {
    "Haugesund – Salg": {
        "script": "run_haugesund.py",
        "args": ["--salg"],
        "outfile": DATA_DIR / "finn_Haugesund_estates.json",
        "icon": "🏠",
    },
    "Haugesund – Leie": {
        "script": "run_haugesund.py",
        "args": ["--leie"],
        "outfile": DATA_DIR / "finn_Haugesund_utleie.json",
        "icon": "🔑",
    },
    "Haugesund – Salg + Leie": {
        "script": "run_haugesund.py",
        "args": [],
        "outfile": DATA_DIR / "finn_Haugesund_estates.json",
        "icon": "📦",
    },
    "Oslo – Salg": {
        "script": "run_oslo.py",
        "args": ["--salg"],
        "outfile": DATA_DIR / "finn_Oslo_estates.json",
        "icon": "🏠",
    },
    "Oslo – Leie": {
        "script": "run_oslo.py",
        "args": ["--leie"],
        "outfile": DATA_DIR / "finn_Oslo_utleie.json",
        "icon": "🔑",
    },
    "Oslo – Salg + Leie": {
        "script": "run_oslo.py",
        "args": [],
        "outfile": DATA_DIR / "finn_Oslo_estates.json",
        "icon": "📦",
    },
}

# ---------------------------------------------------------------------------
# Hjelpefunksjoner
# ---------------------------------------------------------------------------

def _record_count(path: Path) -> int | None:
    """Antall objekter i en JSON-datafil."""
    if not path.exists():
        return None
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        return len(data)
    except Exception:
        return None


def _kommunale_coverage(path: Path) -> tuple[int, int] | None:
    """Returnerer (antall_med_kommunale, totalt) for salgsfiler."""
    if not path.exists():
        return None
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        total = len(data)
        med = sum(
            1 for v in data.values()
            if isinstance(v, dict)
            and v.get("municipality_cost_year") not in (None, float("nan"))
            and not (isinstance(v.get("municipality_cost_year"), float) and math.isnan(v["municipality_cost_year"]))
            and v.get("municipality_cost_year", 0) > 0
        )
        return med, total
    except Exception:
        return None


def _last_modified(path: Path) -> str:
    if not path.exists():
        return "–"
    diff = time.time() - path.stat().st_mtime
    if diff < 60:
        return f"{int(diff)} sek siden"
    elif diff < 3600:
        return f"{int(diff / 60)} min siden"
    elif diff < 86400:
        hours = diff / 3600
        return f"{hours:.1f} t siden"
    else:
        days = int(diff / 86400)
        return f"{days} dag{'er' if days != 1 else ''} siden"


def _process_running() -> bool:
    pid = st.session_state.get("scrape_pid")
    if pid is None:
        return False
    try:
        os.kill(pid, 0)   # sender ikke signal, bare sjekker om prosessen lever
        return True
    except (ProcessLookupError, PermissionError):
        return False


def _start_job(script: str, args: list[str], geocode: bool) -> None:
    """Start skraping som bakgrunnsprosess."""
    cmd = [sys.executable, str(PROJECT_ROOT / script)] + args
    if not geocode:
        cmd.append("--ingen-geo")

    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    log_fh = open(LOG_FILE, "w", encoding="utf-8")

    proc = subprocess.Popen(
        cmd,
        stdout=log_fh,
        stderr=subprocess.STDOUT,
        cwd=str(PROJECT_ROOT),
        text=True,
    )

    st.session_state["scrape_pid"]       = proc.pid
    st.session_state["scrape_proc"]      = proc
    st.session_state["scrape_log_fh"]    = log_fh
    st.session_state["scrape_started"]   = datetime.now().strftime("%H:%M:%S")
    st.session_state["scrape_job_name"]  = st.session_state.get("_job_name", "")


def _stop_job() -> None:
    proc: subprocess.Popen | None = st.session_state.get("scrape_proc")
    if proc:
        try:
            proc.terminate()
        except Exception:
            pass
    fh = st.session_state.get("scrape_log_fh")
    if fh:
        try:
            fh.close()
        except Exception:
            pass
    for key in ["scrape_pid", "scrape_proc", "scrape_log_fh"]:
        st.session_state.pop(key, None)


def _read_log(tail: int = 120) -> str:
    """Les de siste N linjene fra loggfilen."""
    if not LOG_FILE.exists():
        return ""
    try:
        with open(LOG_FILE, encoding="utf-8", errors="replace") as f:
            lines = f.readlines()
        return "".join(lines[-tail:])
    except Exception:
        return ""

# ---------------------------------------------------------------------------
# Status-oversikt: datafiler
# ---------------------------------------------------------------------------

st.subheader("📂 Status – datafiler")

status_files = [
    ("finn_Haugesund_estates.json",  "Haugesund Salg"),
    ("finn_Haugesund_utleie.json",   "Haugesund Leie"),
    ("finn_Oslo_estates.json",       "Oslo Salg"),
    ("finn_Oslo_utleie.json",        "Oslo Leie"),
]

cols = st.columns(len(status_files))
for col, (fname, label) in zip(cols, status_files):
    path = DATA_DIR / fname
    count = _record_count(path)
    modified = _last_modified(path)
    with col:
        if count is not None:
            st.metric(label, f"{count} objekter", delta=f"Oppdatert {modified}")
        else:
            st.metric(label, "Ingen data", delta="Ikke hentet ennå")

# Datakvalitet – kommunale avgifter (kun salgsfiler)
sales_files_status = [(f, l) for f, l in status_files if "utleie" not in f.lower()]
if any((DATA_DIR / f).exists() for f, _ in sales_files_status):
    st.markdown("**📊 Datakvalitet – kommunale avgifter**")
    q_cols = st.columns(len(sales_files_status))
    for col, (fname, label) in zip(q_cols, sales_files_status):
        path = DATA_DIR / fname
        cov = _kommunale_coverage(path)
        with col:
            if cov is not None:
                med, tot = cov
                pct = med / tot * 100 if tot > 0 else 0
                st.metric(
                    f"{label}",
                    f"{med}/{tot} har kom.avg.",
                    delta=f"{pct:.0f}% dekning",
                    delta_color="normal" if pct >= 50 else "inverse",
                )
            else:
                st.metric(label, "—")

st.divider()

# ---------------------------------------------------------------------------
# Jobbvelger og start
# ---------------------------------------------------------------------------

is_running = _process_running()

st.subheader("⚙️ Start ny henting")

left, right = st.columns([2, 1])

with left:
    job_name = st.selectbox(
        "Velg hva som skal hentes",
        list(JOBS.keys()),
        disabled=is_running,
        key="job_select",
    )

with right:
    geocode = st.checkbox(
        "Geocode adresser (krever Geoapify-nøkkel)",
        value=True,
        disabled=is_running,
        help="Henter GPS-koordinater for alle nye adresser via Geoapify API.",
    )

if is_running:
    job_label = st.session_state.get("scrape_job_name", "")
    started   = st.session_state.get("scrape_started", "")
    st.info(f"⏳ **{job_label}** kjører siden {started} – se logg nedenfor.")

    if st.button("⛔ Stopp henting", type="secondary", use_container_width=True):
        _stop_job()
        st.warning("Henting stoppet.")
        st.rerun()
else:
    job_cfg = JOBS[job_name]
    st.markdown(
        f"{job_cfg['icon']} Lagres til: `{job_cfg['outfile'].name}`"
        + ("  \n📍 Geocoding aktivert" if geocode else "  \n⚡ Geocoding deaktivert")
    )

    if st.button(
        f"▶️ Start henting – {job_name}",
        type="primary",
        use_container_width=True,
        disabled=is_running,
    ):
        st.session_state["_job_name"] = job_name
        _start_job(job_cfg["script"], job_cfg["args"], geocode)
        st.success(f"✅ Henting startet! Følg med i loggen nedenfor.")
        time.sleep(0.5)
        st.rerun()

st.divider()

# ---------------------------------------------------------------------------
# Live logg
# ---------------------------------------------------------------------------

st.subheader("📋 Logg")

log_col, btn_col = st.columns([6, 1])

with btn_col:
    if st.button("🔄 Oppdater", use_container_width=True, help="Hent siste logg-output"):
        st.rerun()
    if is_running:
        st.caption("🟢 Kjører")
    elif LOG_FILE.exists():
        st.caption("⚫ Ferdig")

log_text = _read_log(tail=150)

with log_col:
    if log_text:
        # Fremhev feilmeldinger
        display_text = log_text
        st.code(display_text, language=None)

        # Sjekk om jobben er ferdig
        if not is_running and ("✅" in log_text or "ferdig" in log_text.lower()):
            st.success("✅ Henting fullført!")
        elif not is_running and LOG_FILE.exists():
            last_line = log_text.strip().splitlines()[-1] if log_text.strip() else ""
            if last_line:
                st.info(f"Siste linje: {last_line}")
    else:
        st.caption("Ingen logg ennå. Logg vises her etter at du starter en henting.")

# Auto-refresh hvert 5. sekund mens prosessen kjører
if is_running:
    time.sleep(5)
    st.rerun()
