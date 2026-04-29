"""
Kjør full datahenting for Oslo – salg og leie.

Bruk:
    python run_oslo.py              # henter BÅDE salg og leie
    python run_oslo.py --salg       # kun salg
    python run_oslo.py --leie       # kun leie
    python run_oslo.py --ingen-geo  # hopp over geocoding

For å oppdatere data i git:
git add Data/
git commit -m "Oppdater data"
git push

"""
from __future__ import annotations

import argparse
import sys
from typing import Dict

from eiendom_analyse_claude.scrape.search import search_finn_ads
from eiendom_analyse_claude.scrape.ad_parser import get_ad_info
from eiendom_analyse_claude.scrape.utleie_ import get_rental_ad_info
from eiendom_analyse_claude.geo.geocoders import geocode_all
from eiendom_analyse_claude.storage.json_store import save_or_merge
from eiendom_analyse_claude.models import RealEstate, RentalEstate

# -----------------------------------------------------------------------
# Konfigurasjon – endre her ved behov
# -----------------------------------------------------------------------

GEOAPIFY_KEY = "fe0b10a2c8b842969230f26fe492f913"

SALG_URL = (
    "https://www.finn.no/realestate/homes/search.html"
    "?filters=&location=0.20061"
    "&is_new_property=false"
    "&property_type=3&property_type=1&property_type=4&property_type=2"
)
SALG_UT = "Data/finn_Oslo_estates.json"

LEIE_URL = (
    "https://www.finn.no/realestate/lettings/search.html"
    "?filters=&location=0.20061"
    "&property_type=4&property_type=3&property_type=16&property_type=1"
)
LEIE_UT = "Data/finn_Oslo_utleie.json"

MAX_SIDER = 100
GEO_DELAY = 1.0


# -----------------------------------------------------------------------
# Pipeline-funksjoner
# -----------------------------------------------------------------------

def run_salg(geocode: bool = True) -> None:
    print("\n" + "="*50)
    print("  SALG – Oslo")
    print("="*50)

    print("\n[1/4] Henter annonse-URL-er fra FINN...")
    urls = search_finn_ads(SALG_URL, max_pages=MAX_SIDER)
    print(f"      → {len(urls)} annonser funnet")

    print("\n[2/4] Parser annonsene...")
    estates: Dict[str, RealEstate] = {}
    for i, (fk, url) in enumerate(urls.items(), 1):
        obj = get_ad_info(url)
        if obj is None:
            continue
        estates[obj.finnkode] = obj
        if i % 50 == 0:
            print(f"      {i}/{len(urls)} behandlet, {len(estates)} ok")
    print(f"      → {len(estates)} salgsobjekter parsert")

    print(f"\n[3/4] Lagrer/merger til {SALG_UT}...")
    estates = save_or_merge(SALG_UT, estates, RealEstate)
    print(f"      → Totalt {len(estates)} objekter i filen")

    if geocode:
        print("\n[4/4] Geocoder manglende koordinater...")
        geocode_all(
            estates, provider="geoapify",
            delay_seconds=GEO_DELAY,
            max_consecutive_failures=15,
            api_key=GEOAPIFY_KEY,
        )
        save_or_merge(SALG_UT, estates, RealEstate)
        print(f"      → Lagret med koordinater til {SALG_UT}")
    else:
        print("\n[4/4] Geocoding hoppet over (--ingen-geo)")

    print("\n✅ Salg Oslo ferdig!\n")


def run_leie(geocode: bool = True) -> None:
    print("\n" + "="*50)
    print("  LEIE – Oslo")
    print("="*50)

    print("\n[1/4] Henter annonse-URL-er fra FINN...")
    urls = search_finn_ads(LEIE_URL, max_pages=MAX_SIDER)
    print(f"      → {len(urls)} annonser funnet")

    print("\n[2/4] Parser annonsene...")
    rentals: Dict[str, RentalEstate] = {}
    for i, (fk, url) in enumerate(urls.items(), 1):
        obj = get_rental_ad_info(url)
        if obj is None:
            continue
        rentals[obj.finnkode] = obj
        if i % 50 == 0:
            print(f"      {i}/{len(urls)} behandlet, {len(rentals)} ok")
    print(f"      → {len(rentals)} leieobjekter parsert")

    print(f"\n[3/4] Lagrer/merger til {LEIE_UT}...")
    rentals = save_or_merge(LEIE_UT, rentals, RentalEstate)
    print(f"      → Totalt {len(rentals)} objekter i filen")

    if geocode:
        print("\n[4/4] Geocoder manglende koordinater...")
        geocode_all(
            rentals, provider="geoapify",
            delay_seconds=GEO_DELAY,
            max_consecutive_failures=15,
            api_key=GEOAPIFY_KEY,
        )
        save_or_merge(LEIE_UT, rentals, RentalEstate)
        print(f"      → Lagret med koordinater til {LEIE_UT}")
    else:
        print("\n[4/4] Geocoding hoppet over (--ingen-geo)")

    print("\n✅ Leie Oslo ferdig!\n")


# -----------------------------------------------------------------------
# Inngangspunkt
# -----------------------------------------------------------------------

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Hent FINN-data for Oslo")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--salg",  action="store_true", help="Kun salgsannonser")
    group.add_argument("--leie",  action="store_true", help="Kun leieannonser")
    parser.add_argument("--ingen-geo", action="store_true", help="Hopp over geocoding")
    args = parser.parse_args()

    geocode = not args.ingen_geo

    if args.salg:
        run_salg(geocode)
    elif args.leie:
        run_leie(geocode)
    else:
        run_salg(geocode)
        run_leie(geocode)
