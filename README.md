# Eiendomsanalyse Claude

Forbedret versjon av eiendomsanalyseplattformen – bygget på toppen av `eiendom_analyse_pro`.

## Nyheter i denne versjonen

- **Multi-side Streamlit-app** med 4 separate analysevisninger
- **Kontantstrømsanalyse** med fullt konfigurerbar UI (rente, egenkapital, felleskost, strøm, osv.)
- **Markedsoversikt** med histogrammer, energimerkefordeling og boligtypefordeling
- **Eiendom Detaljer** – søk opp enkeltboliger og se nabosammenligning
- **Boligtype-felt** (`property_type`) lagres nå i RealEstate og RentalEstate
- **Tittel-felt** (`title`) lagres i begge dataklasser
- **Retry-logikk** i HTTP-klient (med backoff, rate-limiting og sesjon-gjenbruk)
- **Bedre JSON-lagring** – NaN → null for gyldig JSON, bakoverkompatibel lasting
- **Gap i prosent** (`gap_pct`) i tillegg til absolutt gap

## Instalasjon

```bash
cd eiendomsanalyse_claude
pip install -r requirements.txt
```

## Kjøre dashbordet

```bash
streamlit run app.py
```

## Hente data fra FINN

```bash
# Salg – Haugesund
python -m eiendom_analyse_claude.cli.gather \
    --search-url "https://www.finn.no/realestate/homes/search.html?location=1.20012.20197" \
    --out Data/finn_Haugesund_estates.json \
    --type salg

# Leie – Haugesund
python -m eiendom_analyse_claude.cli.gather \
    --search-url "https://www.finn.no/realestate/lettings/search.html?location=1.20012.20197" \
    --out Data/finn_Haugesund_utleie.json \
    --type leie

# Salg – Oslo
python -m eiendom_analyse_claude.cli.gather \
    --search-url "https://www.finn.no/realestate/homes/search.html?location=1.20061.20512" \
    --out Data/finn_Oslo_estates.json \
    --type salg

# Geocode (krever Geoapify API-nøkkel)
export GEOAPIFY_API_KEY="din_nøkkel"
python -m eiendom_analyse_claude.cli.geocode \
    --in Data/finn_Haugesund_estates.json \
    --out Data/finn_Haugesund_estates.json
```

## Prosjektstruktur

```
eiendomsanalyse_claude/
├── app.py                          # Hoved-Streamlit-app
├── pages/
│   ├── 1_Prisgap.py               # Nabobasert prisanalyse
│   ├── 2_Kontantstrom.py          # Kontantstrøm & avkastning
│   ├── 3_Markedsoversikt.py       # Statistikk & distribusjoner
│   └── 4_Eiendom_Detaljer.py      # Enkeltbolig-søk
├── eiendom_analyse_claude/
│   ├── models.py                   # RealEstate, RentalEstate
│   ├── scrape/                     # FINN-scraping
│   ├── geo/                        # Geocoding & naboberegning
│   ├── analysis/                   # Prisgap, kontantstrøm
│   ├── storage/                    # JSON-lagring
│   ├── utils/                      # HTTP med retry
│   └── cli/                        # Kommandolinjeverktøy
├── Data/                           # JSON-datafiler
├── requirements.txt
└── pyproject.toml
```

## Merknad

Respekter FINNs brukervilkår og robots.txt.
Geocoding-leverandører har rategrenser – bruk caching og forsinkelser.
