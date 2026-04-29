from __future__ import annotations

import re
import math
from bs4 import BeautifulSoup

from eiendom_analyse_claude.models import RealEstate
from eiendom_analyse_claude.utils.http import get, HttpConfig


FINNKODE_RE = re.compile(r"finnkode=(\d+)")


# ---------------------------------------------------------------------------
# Tekst-parsere
# ---------------------------------------------------------------------------

def _extract_int(text: str | None) -> float:
    if not text:
        return math.nan
    m = re.search(r"\d+", text)
    return float(m.group(0)) if m else math.nan


def _extract_float(text: str | None) -> float:
    if not text:
        return math.nan
    normalized = text.replace(",", ".")
    m = re.search(r"\d+(\.\d+)?", normalized)
    return float(m.group(0)) if m else math.nan


def _extract_price(text: str | None) -> float:
    """Henter NOK-beløp fra strenger som '4 990 000 kr'."""
    if not text:
        return math.nan
    digits = re.sub(r"[^\d]", "", text)
    return float(digits) if digits else math.nan


def _get_bold_value(container) -> str | None:
    """FINN bruker ofte bold span/dd for verdier."""
    if not container:
        return None
    tag = (
        container.find("span", class_=lambda c: c and "font-bold" in c.split())
        or container.find("dd", class_=lambda c: c and "font-bold" in c.split())
        or container.find("dd")
        or container.find("span")
    )
    return tag.get_text(strip=True) if tag else None


def _get_text_by_testid(soup, testid: str) -> str | None:
    el = soup.find(attrs={"data-testid": testid})
    if el:
        t = el.get_text(" ", strip=True)
        return t or None
    return None


# ---------------------------------------------------------------------------
# Hoved-funksjon
# ---------------------------------------------------------------------------

def get_ad_info(url: str, http_cfg: HttpConfig | None = None) -> RealEstate | None:
    """
    Last ned én FINN-annonse og parse den til et RealEstate-objekt.

    Returnerer None hvis:
    - Prisantydning er et intervall
    - Siden ikke kan hentes
    """
    m = FINNKODE_RE.search(url)
    if not m:
        raise ValueError(f"URL mangler finnkode parameter: {url}")
    finnkode = m.group(1)

    try:
        resp = get(url, cfg=http_cfg)
    except Exception as e:
        print(f"[annonse] Kunne ikke hente {url}: {e}")
        return None

    soup = BeautifulSoup(resp.text, "html.parser")

    # --- Tittel ---
    title = _get_text_by_testid(soup, "object-title")

    # --- Boligtype ---
    property_type = None
    pt = soup.find(attrs={"data-testid": "info-property-type"})
    property_type = _get_bold_value(pt)

    # --- Adresse ---
    location = _get_text_by_testid(soup, "object-address")

    # --- Priser ---
    pricing_map = {
        "asking_price":          "pricing-incicative-price",
        "total_price":           "pricing-total-price",
        "registration_charge":   "pricing-registration-charge",
        "joint_debt":            "pricing-joint-debt",
        "common_monthly_cost":   "pricing-common-monthly-cost",
        "collective_assets":     "pricing-collective-assets",
        "tax_value_formueverdi": "pricing-tax-value",
    }

    prices: dict[str, float] = {k: math.nan for k in pricing_map}
    for fld, testid in pricing_map.items():
        container = soup.find(attrs={"data-testid": testid})
        raw = _get_bold_value(container)
        if not raw:
            continue
        if fld == "asking_price" and ("-" in raw or "–" in raw):
            print(f"[annonse] Hopper over {finnkode}: prisantydning er intervall ({raw!r})")
            return None
        prices[fld] = _extract_price(raw)

    # --- Kommunale avgifter ---
    # FINN bruker ulike testid-er avhengig av boligtype og side-versjon.
    # Vi prøver kjente testid-er, deretter tekst-basert fallback.
    # Rimelighetsgrense: kommunale avgifter i Norge er 500–80 000 kr/år.
    _KOM_MIN =     500.0
    _KOM_MAX =  80_000.0

    def _is_reasonable_kom(val: float) -> bool:
        return not math.isnan(val) and _KOM_MIN <= val <= _KOM_MAX

    kommunale_avgifter = math.nan
    _kom_testids = [
        "pricing-municipal-fees",        # vanligst per 2024/2025
        "pricing-communal-charges",
        "pricing-municipal-charges",
        "pricing-municipal-tax",
        "pricing-communal-tax",
        "info-communal-charges",
        "info-municipal-charges",
        "info-municipal-tax",
    ]
    for testid in _kom_testids:
        container = soup.find(attrs={"data-testid": testid})
        raw = _get_bold_value(container)
        if raw:
            val = _extract_price(raw)
            if _is_reasonable_kom(val):
                kommunale_avgifter = val
                break

    # Fallback: søk etter label-tekst "kommunal" i hele siden.
    # NB: bruk kun direkte søsken – IKKE _get_bold_value(parent) som kan
    #     finne feil bold-element (f.eks. prisantydning) langt oppe i treet.
    if math.isnan(kommunale_avgifter):
        for tag in soup.find_all(["dt", "th", "span", "div", "p"]):
            label = tag.get_text(strip=True).lower()
            if "kommunal" not in label:
                continue
            # Kun se på direkte søsken, ikke hele parent-treet
            for sibling in tag.find_next_siblings():
                raw = sibling.get_text(strip=True)
                val = _extract_price(raw)
                if _is_reasonable_kom(val):
                    kommunale_avgifter = val
                    break
            if not math.isnan(kommunale_avgifter):
                break

    # --- Nøkkelinfo (tall) ---
    keyinfo_map = {
        "bedrooms":          ("info-bedrooms",          _extract_int),
        "rooms":             ("info-rooms",              _extract_int),
        "area":              ("info-usable-area",        _extract_float),
        "internal_area":     ("info-usable-i-area",      _extract_float),
        "external_area":     ("info-usable-e-area",      _extract_float),
        "balcony_area":      ("info-usable-b-area",      _extract_float),
        "floor":             ("info-floor",              _extract_int),
        "construction_year": ("info-construction-year",  _extract_int),
    }

    parsed: dict[str, float] = {k: math.nan for k in keyinfo_map}
    for fld, (testid, parser) in keyinfo_map.items():
        container = soup.find(attrs={"data-testid": testid})
        raw = _get_bold_value(container)
        if raw:
            parsed[fld] = float(parser(raw))

    # --- Energimerking ---
    energy_label = None
    e = soup.find(attrs={"data-testid": "energy-label"})
    if e:
        energy_label = _get_bold_value(e)

    return RealEstate(
        finnkode=finnkode,
        url=url,
        title=title,
        property_type=property_type,
        location=location,
        bedrooms=parsed["bedrooms"],
        rooms=parsed["rooms"],
        floor=parsed["floor"],
        construction_year=parsed["construction_year"],
        energy_label=energy_label,
        area=parsed["area"],
        internal_area=parsed["internal_area"],
        external_area=parsed["external_area"],
        balcony_area=parsed["balcony_area"],
        asking_price=prices["asking_price"],
        total_price=prices["total_price"],
        registration_charge=prices["registration_charge"],
        joint_debt=prices["joint_debt"],
        common_monthly_cost=prices["common_monthly_cost"],
        municipality_cost_year=kommunale_avgifter,
        collective_assets=prices["collective_assets"],
        tax_value_formueverdi=prices["tax_value_formueverdi"],
    )
