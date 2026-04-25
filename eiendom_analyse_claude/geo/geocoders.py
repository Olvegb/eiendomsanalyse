from __future__ import annotations

import math
import os
import time
from dataclasses import dataclass

import requests


@dataclass(frozen=True)
class GeoResult:
    latitude: float
    longitude: float


def _nan_result() -> GeoResult:
    return GeoResult(latitude=math.nan, longitude=math.nan)


def geoapify_geocode(address: str, api_key: str | None = None, timeout_s: float = 10.0) -> GeoResult:
    """
    Geocode med Geoapify.

    API-nøkkel fra argument eller env-var GEOAPIFY_API_KEY.
    """
    if not address:
        return _nan_result()

    api_key = api_key or os.getenv("GEOAPIFY_API_KEY")
    if not api_key:
        print("[geo] Mangler GEOAPIFY_API_KEY")
        return _nan_result()

    url = "https://api.geoapify.com/v1/geocode/search"
    params = {
        "text": address,
        "format": "json",
        "limit": 1,
        "lang": "no",
        "apiKey": api_key,
    }

    try:
        r = requests.get(url, params=params, timeout=timeout_s)
        r.raise_for_status()
        data = r.json()
    except Exception as e:
        print(f"[geo] Geoapify feil for {address!r}: {e}")
        return _nan_result()

    results = data.get("results") or []
    if not results:
        return _nan_result()

    top = results[0]
    try:
        return GeoResult(latitude=float(top["lat"]), longitude=float(top["lon"]))
    except Exception:
        return _nan_result()


def geocode_all(
    estates: dict[str, object],
    *,
    provider: str = "geoapify",
    delay_seconds: float = 1.0,
    max_consecutive_failures: int = 10,
    api_key: str | None = None,
    verbose: bool = True,
) -> None:
    """
    Geocode manglende koordinater in-place, med adresse-cache.
    Fungerer for både RealEstate og RentalEstate.
    """
    address_cache: dict[str, tuple[float, float]] = {}
    geocoded = 0
    skipped = 0

    # Forvarm cache fra objekter som allerede har koordinater
    for est in estates.values():
        loc = getattr(est, "location", None)
        if not loc:
            continue
        if hasattr(est, "has_valid_coordinates") and est.has_valid_coordinates():
            address_cache[loc] = (float(est.latitude), float(est.longitude))

    failures = 0

    for fk, est in estates.items():
        loc = getattr(est, "location", None)
        if not loc:
            skipped += 1
            continue

        if hasattr(est, "has_valid_coordinates") and est.has_valid_coordinates():
            skipped += 1
            continue

        if loc in address_cache:
            est.latitude, est.longitude = address_cache[loc]
            geocoded += 1
            continue

        if failures >= max_consecutive_failures:
            print(f"[geo] Stopper: for mange feil ({failures} på rad).")
            break

        if provider == "geoapify":
            res = geoapify_geocode(loc, api_key)
        else:
            raise ValueError(f"Ukjent provider: {provider}")

        if math.isnan(res.latitude):
            failures += 1
            if verbose:
                print(f"[geo] Fant ikke koordinater for: {loc!r}")
        else:
            failures = 0
            est.latitude = res.latitude
            est.longitude = res.longitude
            address_cache[loc] = (res.latitude, res.longitude)
            geocoded += 1
            if verbose:
                print(f"[geo] ✅ {loc!r} -> ({res.latitude:.4f}, {res.longitude:.4f})")

        time.sleep(delay_seconds)

    if verbose:
        print(f"[geo] Ferdig: geocodet={geocoded}, hoppet over={skipped}")
