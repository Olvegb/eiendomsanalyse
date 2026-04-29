"""
Overview – Datahenting fra FINN (hjemmeside).
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

import streamlit as st

st.title("🔄 Datahenting fra FINN")
st.markdown(
    "Start og følg med på innhenting av boligannonser direkte herfra. "
    "Skrapingen kjører i bakgrunnen – du kan navigere fritt i appen mens den jobber."
)

# ---------------------------------------------------------------------------
# Konfig
# ---------------------------------------------------------------------------

PROJECT_ROOT = Path(__file__).parent.parent
DATA_DIR = PROJECT_ROOT / "Data"
LOG_FILE = DATA_DIR / "scrape_log.txt"

PREDEFINED_JOBS = {
    "Haugesund – Salg":        {"script": "run_haugesund.py", "args": ["--salg"]},
    "Haugesund – Leie":        {"script": "run_haugesund.py", "args": ["--leie"]},
    "Haugesund – Salg + Leie": {"script": "run_haugesund.py", "args": []},
    "Oslo – Salg":             {"script": "run_oslo.py",      "args": ["--salg"]},
    "Oslo – Leie":             {"script": "run_oslo.py",      "args": ["--leie"]},
    "Oslo – Salg + Leie":      {"script": "run_oslo.py",      "args": []},
    "Bergen – Salg":           {"script": "run_bergen.py",    "args": ["--salg"]},
    "Bergen – Leie":           {"script": "run_bergen.py",    "args": ["--leie"]},
    "Bergen – Salg + Leie":    {"script": "run_bergen.py",    "args": []},
}

# ---------------------------------------------------------------------------
# Hjelpefunksjoner
# ---------------------------------------------------------------------------

def _record_count(path: Path) -> int | None:
    if not path.exists():
        return None
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        return len(data)
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
        return f"{diff / 3600:.1f} t siden"
    else:
        days = int(diff / 86400)
        return f"{days} dag{'er' if days != 1 else ''} siden"


def _process_running() -> bool:
    pid = st.session_state.get("scrape_pid")
    if pid is None:
        return False
    try:
        os.kill(pid, 0)
        return True
    except (ProcessLookupError, PermissionError):
        return False


def _launch(cmd: list[str], label: str) -> None:
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
    st.session_state["scrape_job_label"] = label


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


def _read_log(tail: int = 150) -> str:
    if not LOG_FILE.exists():
        return ""
    try:
        with open(LOG_FILE, encoding="utf-8", errors="replace") as f:
            lines = f.readlines()
        return "".join(lines[-tail:])
    except Exception:
        return ""


def _pretty_label(filename: str) -> str:
    name = filename.replace("finn_", "").replace(".json", "")
    name = name.replace("_estates", " Salg").replace("_utleie", " Leie")
    return name.replace("_", " ")

# ---------------------------------------------------------------------------
# Status – alle JSON-filer i Data/
# ---------------------------------------------------------------------------

st.subheader("📂 Status – datafiler")

DATA_DIR.mkdir(parents=True, exist_ok=True)
json_files = sorted(DATA_DIR.glob("*.json"))

if json_files:
    cols = st.columns(min(len(json_files), 4))
    for i, path in enumerate(json_files):
        count    = _record_count(path)
        modified = _last_modified(path)
        label    = _pretty_label(path.name)
        with cols[i % 4]:
            if count is not None:
                st.metric(label, f"{count} objekter", delta=f"Oppdatert {modified}")
            else:
                st.metric(label, "Ingen data", delta="Ikke hentet ennå")
else:
    st.info("Ingen JSON-datafiler funnet i `Data/` ennå. Start en henting nedenfor.")

st.divider()

# ---------------------------------------------------------------------------
# Henting
# ---------------------------------------------------------------------------

is_running = _process_running()

st.subheader("⚙️ Henting")

if is_running:
    job_label = st.session_state.get("scrape_job_label", "")
    started   = st.session_state.get("scrape_started", "")
    st.info(f"⏳ **{job_label}** kjører siden {started} – se logg nedenfor.")
    if st.button("⛔ Stopp henting", type="secondary", use_container_width=True):
        _stop_job()
        st.warning("Henting stoppet.")
        st.rerun()

# ----- Forhåndslagrede jobber -----
with st.expander("📋 Forhåndslagrede jobber", expanded=not is_running):
    left, right = st.columns([2, 1])
    with left:
        job_name = st.selectbox(
            "Velg by og type",
            list(PREDEFINED_JOBS.keys()),
            disabled=is_running,
            key="job_select",
        )
    with right:
        geocode = st.checkbox(
            "Geocode adresser",
            value=True,
            disabled=is_running,
            help="Henter GPS-koordinater via Geoapify.",
        )

    if st.button(
        f"▶️ Start – {job_name}",
        type="primary",
        use_container_width=True,
        disabled=is_running,
        key="start_predefined",
    ):
        cfg = PREDEFINED_JOBS[job_name]
        cmd = [sys.executable, str(PROJECT_ROOT / cfg["script"])] + cfg["args"]
        if not geocode:
            cmd.append("--ingen-geo")
        _launch(cmd, job_name)
        st.success(f"✅ Startet: {job_name}")
        time.sleep(0.5)
        st.rerun()

# ----- Ny henting (valgfri URL) -----
st.markdown("#### Ny henting")

salg_tab, leie_tab = st.tabs(["🏠 Salg", "🔑 Leie"])

with salg_tab:
    salg_url = st.text_input(
        "FINN søke-URL (salg)",
        placeholder="https://www.finn.no/realestate/homes/search.html?location=...",
        key="salg_url",
        disabled=is_running,
    )
    salg_filename = st.text_input(
        "JSON-filnavn (uten .json)",
        placeholder="finn_Stavanger_estates",
        key="salg_filename",
        disabled=is_running,
    )
    if st.button("▶️ Start salgs-henting", type="primary", use_container_width=True,
                 disabled=is_running, key="start_salg"):
        if not salg_url.strip():
            st.error("Du må oppgi en FINN søke-URL.")
        elif not salg_filename.strip():
            st.error("Du må oppgi et filnavn.")
        else:
            fn  = salg_filename.strip().removesuffix(".json")
            out = f"Data/{fn}.json"
            cmd = [
                sys.executable, "-m", "eiendom_analyse_claude.cli.gather",
                "--search-url", salg_url.strip(),
                "--out", out,
                "--type", "salg",
            ]
            _launch(cmd, f"Salg → {out}")
            st.success(f"✅ Startet! Lagres til `{out}`")
            time.sleep(0.5)
            st.rerun()

with leie_tab:
    leie_url = st.text_input(
        "FINN søke-URL (leie)",
        placeholder="https://www.finn.no/realestate/lettings/search.html?location=...",
        key="leie_url",
        disabled=is_running,
    )
    leie_filename = st.text_input(
        "JSON-filnavn (uten .json)",
        placeholder="finn_Stavanger_utleie",
        key="leie_filename",
        disabled=is_running,
    )
    if st.button("▶️ Start leie-henting", type="primary", use_container_width=True,
                 disabled=is_running, key="start_leie"):
        if not leie_url.strip():
            st.error("Du må oppgi en FINN søke-URL.")
        elif not leie_filename.strip():
            st.error("Du må oppgi et filnavn.")
        else:
            fn  = leie_filename.strip().removesuffix(".json")
            out = f"Data/{fn}.json"
            cmd = [
                sys.executable, "-m", "eiendom_analyse_claude.cli.gather",
                "--search-url", leie_url.strip(),
                "--out", out,
                "--type", "leie",
            ]
            _launch(cmd, f"Leie → {out}")
            st.success(f"✅ Startet! Lagres til `{out}`")
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
        st.code(log_text, language=None)
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
