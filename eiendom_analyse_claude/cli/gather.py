"""
CLI: Hent og parse FINN-annonser.

Eksempel:
    python -m eiendom_analyse_claude.cli.gather \\
        --search-url "https://www.finn.no/realestate/homes/search.html?..." \\
        --out "Data/finn_oslo_estates.json" \\
        --type salg \\
        --max-pages 60
"""
from __future__ import annotations

import argparse
import sys
from typing import Dict

from eiendom_analyse_claude.scrape.search import search_finn_ads
from eiendom_analyse_claude.scrape.ad_parser import get_ad_info
from eiendom_analyse_claude.scrape.utleie_ import get_rental_ad_info
from eiendom_analyse_claude.storage.json_store import save_or_merge
from eiendom_analyse_claude.models import RealEstate, RentalEstate


def main(argv=None):
    parser = argparse.ArgumentParser(description="Hent FINN-annonser")
    parser.add_argument("--search-url", required=True, help="FINN søke-URL")
    parser.add_argument("--out", required=True, help="Utdatafil (.json)")
    parser.add_argument("--type", choices=["salg", "leie"], default="salg", help="Annonse-type")
    parser.add_argument("--max-pages", type=int, default=60)
    parser.add_argument("--quiet", action="store_true", help="Suppres output")
    args = parser.parse_args(argv)

    verbose = not args.quiet

    if verbose:
        print(f"🔍 Henter annonse-URL-er fra FINN ({'salg' if args.type == 'salg' else 'leie'})...")

    ad_urls = search_finn_ads(args.search_url, max_pages=args.max_pages, verbose=verbose)

    if verbose:
        print(f"✅ Fant {len(ad_urls)} annonser. Parser detaljer...")

    estates: Dict = {}
    model_cls = RealEstate if args.type == "salg" else RentalEstate
    parser_fn = get_ad_info if args.type == "salg" else get_rental_ad_info

    for i, (fk, url) in enumerate(ad_urls.items(), 1):
        obj = parser_fn(url)
        if obj is None:
            continue
        estates[obj.finnkode] = obj
        if verbose and i % 50 == 0:
            print(f"   {i}/{len(ad_urls)} behandlet, {len(estates)} ok")

    if verbose:
        print(f"💾 Lagrer {len(estates)} objekter til {args.out} (merge med eksisterende)...")

    save_or_merge(args.out, estates, model_cls)

    if verbose:
        print("✅ Ferdig!")


if __name__ == "__main__":
    main()
