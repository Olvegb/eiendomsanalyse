"""
Kontantstrøm- og avkastningsanalyse for utleieeiendommer.

Bygger på og utvider logikken fra eiendom_analyse_pro/Utleie.py.
"""
from __future__ import annotations

import math
from typing import Optional

import numpy as np

from eiendom_analyse_claude.models import RealEstate, RentalEstate
from eiendom_analyse_claude.geo.neighbors import build_balltree, query_neighbors_indices
from eiendom_analyse_claude.analysis.cashflow_params import CashflowParams, CashflowResult  # noqa: F401


# ---------------------------------------------------------------------------
# Beregningsfunksjoner
# ---------------------------------------------------------------------------

def avg_rental_per_m2(
    sales: dict[str, RealEstate],
    rentals: dict[str, RentalEstate],
    radius_m: float = 1000,
) -> dict[str, float]:
    """
    For hvert salgsobjekt: beregn gjennomsnitts leie per m² fra naboer.

    Returnerer dict finnkode -> gjennomsnittlig leie/m²/mnd.
    """
    sales_list = [e for e in sales.values() if e.has_valid_coordinates()]
    rentals_list = [
        r for r in rentals.values()
        if r.has_valid_coordinates()
        and not math.isnan(r.primary_area)
        and r.primary_area > 0
        and not math.isnan(r.monthly_rent)
        and r.monthly_rent > 0
    ]

    if not rentals_list or not sales_list:
        return {}

    r_lats = np.array([r.latitude for r in rentals_list])
    r_lons = np.array([r.longitude for r in rentals_list])
    s_lats = np.array([e.latitude for e in sales_list])
    s_lons = np.array([e.longitude for e in sales_list])

    tree = build_balltree(r_lats, r_lons)
    neighbor_idxs = query_neighbors_indices(tree, s_lats, s_lons, radius_m)

    results: dict[str, float] = {}
    for sale, idxs in zip(sales_list, neighbor_idxs):
        vals = [
            rentals_list[i].monthly_rent / rentals_list[i].primary_area
            for i in idxs
            if rentals_list[i].primary_area > 0
        ]
        if vals:
            results[sale.finnkode] = float(np.mean(vals))

    return results


def _energy_factor(label: Optional[str], factors: list[float]) -> float:
    if not label:
        return 1.0
    c = label[0].upper()
    idx = ord(c) - ord("A")
    if 0 <= idx < len(factors):
        return factors[idx]
    return 1.0


def _annuity_payment(principal: float, annual_rate: float, years: int) -> float:
    """Månedlig annuitetsbetaling -> returnerer ÅRSBELØP."""
    if years <= 0 or annual_rate <= 0:
        return 0.0
    r = annual_rate / 12
    n = years * 12
    monthly = principal * r / (1 - (1 + r) ** -n)
    return monthly * 12


def compute_cashflow(
    sale: RealEstate,
    rent_per_m2_monthly: float,
    p: CashflowParams,
) -> CashflowResult:
    """
    Beregn full kontantstrøm for én eiendom.
    """
    sales_price = sale.total_price if not math.isnan(sale.total_price) else sale.asking_price
    area = sale.area if not math.isnan(sale.area) else 0.0
    loan = max(0.0, sales_price - p.equity)

    # Leie
    est_rent = rent_per_m2_monthly * area
    gross_rent_year = est_rent * (12 - p.vacancy_months)

    # Renter
    interest_year = loan * p.interest_rate

    # Avdrag (annuitet)
    if p.interest_only or loan <= 0:
        principal_year = 0.0
    else:
        total_payment_year = _annuity_payment(loan, p.interest_rate, p.loan_years)
        principal_year = max(0.0, total_payment_year - interest_year)

    # Strøm
    if p.tenant_pays_electricity:
        electricity_year = 0.0
    else:
        ef = _energy_factor(sale.energy_label, p.energy_factor)
        electricity_year = p.kwh_per_m2 * area * p.electricity_price * ef

    # Felleskostnader
    common_cost_year = (
        sale.common_monthly_cost * 12
        if not math.isnan(sale.common_monthly_cost)
        else 0.0
    )

    # Kommunale avgifter (NOK/år)
    kommunale_avgifter_year = (
        sale.municipality_cost_year
        if not math.isnan(sale.municipality_cost_year)
        else 0.0
    )

    maintenance_year = p.maintenance_pct_rent * est_rent * 12

    total_costs_excl_principal = (
        interest_year
        + p.insurance
        + p.tax
        + maintenance_year
        + electricity_year
        + common_cost_year
        + kommunale_avgifter_year
    )

    netto = gross_rent_year - total_costs_excl_principal
    gross_yield = (gross_rent_year / sales_price * 100) if sales_price > 0 else 0.0
    net_yield = (netto / sales_price * 100) if sales_price > 0 else 0.0
    roi = (netto / p.equity * 100) if p.equity > 0 else 0.0

    return CashflowResult(
        finnkode=sale.finnkode,
        sales_price=sales_price,
        area=area,
        estimated_rent_monthly=est_rent,
        energy_label=sale.energy_label,
        gross_rent_year=gross_rent_year,
        interest_year=interest_year,
        principal_year=principal_year,
        insurance_year=p.insurance,
        tax_year=p.tax,
        maintenance_year=maintenance_year,
        electricity_year=electricity_year,
        common_cost_year=common_cost_year,
        kommunale_avgifter_year=kommunale_avgifter_year,
        netto_cashflow_year=netto,
        gross_yield_pct=gross_yield,
        net_yield_pct=net_yield,
        roi_pct=roi,
    )


def run_cashflow_analysis(
    sales: dict[str, RealEstate],
    rentals: dict[str, RentalEstate],
    p: CashflowParams,
    radius_m: float = 1000,
) -> list[CashflowResult]:
    """
    Kjør full kontantstrømsanalyse for alle salgsobjekter.

    Bruker nabobasert leieestimering der mulig, ellers p.default_rent_per_m2.
    """
    rent_map = avg_rental_per_m2(sales, rentals, radius_m)

    results = []
    for fk, sale in sales.items():
        if math.isnan(sale.total_price) and math.isnan(sale.asking_price):
            continue
        if math.isnan(sale.area) or sale.area <= 0:
            continue

        rent_pm2 = rent_map.get(fk, p.default_rent_per_m2)
        result = compute_cashflow(sale, rent_pm2, p)
        results.append(result)

    return results
