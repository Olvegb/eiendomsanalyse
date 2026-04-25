"""
CLI: Geocode adresser i en JSON-fil.

Eksempel:
    python -m eiendom_analyse_claude.cli.geocode \\
        --in Data/finn_oslo_estates.json \\
        --out Data/finn_oslo_estates.json \\
        --type salg
"""
from __future__ import annotations

import argparse
import os

from eiendom_analyse_claude.geo.geocoders import geocode_all
from eiendom_analyse_claude.storage.json_store import load_objects, save_estates
from eiendom_analyse_claude.models import RealEstate, RentalEstate


def main(argv=None):
    parser = argparse.ArgumentParser(description="Geocode FINN-annonser")
    parser.add_argument("--in", dest="infile", required=True)
    parser.add_argument("--out", dest="outfile", required=True)
    parser.add_argument("--type", choices=["salg", "leie"], default="salg")
    parser.add_argument("--api-key", default=None, help="Geoapify API-nøkkel")
    parser.add_argument("--delay", type=float, default=1.0)
    args = parser.parse_args(argv)

    model_cls = RealEstate if args.type == "salg" else RentalEstate
    api_key = args.api_key or os.getenv("GEOAPIFY_API_KEY")

    print(f"📍 Laster {args.infile}...")
    estates = load_objects(args.infile, model_cls)
    print(f"   {len(estates)} objekter lastet")

    print("🗺️  Geocoder manglende koordinater...")
    geocode_all(
        estates,
        provider="geoapify",
        delay_seconds=args.delay,
        api_key=api_key,
        verbose=True,
    )

    print(f"💾 Lagrer til {args.outfile}...")
    save_estates(args.outfile, estates)
    print("✅ Ferdig!")


if __name__ == "__main__":
    main()
