from __future__ import annotations

import math
import re
from bs4 import BeautifulSoup

from eiendom_analyse_claude.models import RentalEstate
from eiendom_analyse_claude.utils.http import get, HttpConfig

FINNKODE_RE = re.compile(r"finnkode=(\d+)")


def _extract_price(text: str | None) -> float:
    if not text:
        return math.nan
    digits = re.sub(r"[^\d]", "", text)
    return float(digits) if digits else math.nan


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


def _get_bold_value(container) -> str | None:
    if not container:
        return None
    tag = (
        container.find("span", class_=lambda c: c and "font-bold" in c.split())
        or container.find("dd", class_=lambda c: c and "font-bold" in c.split())
        or container.find("dd")
        or container.find("span")
    )
    return tag.get_text(strip=True) if tag else None


def get_rental_ad_info(url: str, http_cfg: HttpConfig | None = None) -> RentalEstate | None:
    """
    Last ned én FINN-leieannonse og parse den til RentalEstate.
    """
    m = FINNKODE_RE.search(url)
    if not m:
        raise ValueError(f"URL mangler finnkode parameter: {url}")
    finnkode = m.group(1)

    try:
        resp = get(url, cfg=http_cfg)
    except Exception as e:
        print(f"[leie] Kunne ikke hente {url}: {e}")
        return None

    soup = BeautifulSoup(resp.text, "html.parser")

    # Tittel
    title = None
    t = soup.find(attrs={"data-testid": "object-title"})
    if t:
        title = t.get_text(" ", strip=True) or None

    # Adresse
    location = None
    lt = soup.find(attrs={"data-testid": "object-address"})
    if lt:
        location = lt.get_text(" ", strip=True) or None

    # Boligtype
    property_type = None
    pt = soup.find(attrs={"data-testid": "info-property-type"})
    property_type = _get_bold_value(pt)

    # Priser
    pricing_map = {
        "monthly_rent": "pricing-common-monthly-cost",
        "deposit":      "pricing-deposit",
    }
    prices = {k: math.nan for k in pricing_map}
    for fld, testid in pricing_map.items():
        container = soup.find(attrs={"data-testid": testid})
        raw = _get_bold_value(container)
        if raw:
            prices[fld] = _extract_price(raw)

    # Nøkkelinfo (tall)
    keyinfo_numeric = {
        "bedrooms": ("info-bedrooms", _extract_int),
        "floor":    ("info-floor",    _extract_int),
    }
    parsed = {k: math.nan for k in keyinfo_numeric}
    for fld, (testid, parser) in keyinfo_numeric.items():
        container = soup.find(attrs={"data-testid": testid})
        raw = _get_bold_value(container)
        if raw:
            parsed[fld] = float(parser(raw))

    # Areal (prioritert rekkefølge: BRA-i > Primærrom > Bruksareal)
    area_candidates = (
        "info-usable-i-area",
        "info-primary-area",
        "info-usable-area",
    )
    primary_area = math.nan
    for testid in area_candidates:
        container = soup.find(attrs={"data-testid": testid})
        raw = _get_bold_value(container)
        if raw:
            v = _extract_float(raw)
            if not math.isnan(v):
                primary_area = v
                break

    # Leieperiode
    lease_period = None
    ts = soup.find(attrs={"data-testid": "info-timespan"})
    raw_ts = _get_bold_value(ts)
    if raw_ts:
        lease_period = raw_ts

    return RentalEstate(
        finnkode=finnkode,
        url=url,
        title=title,
        location=location,
        property_type=property_type,
        monthly_rent=prices["monthly_rent"],
        deposit=prices["deposit"],
        primary_area=primary_area,
        bedrooms=parsed["bedrooms"],
        floor=parsed["floor"],
        lease_period=lease_period,
    )
