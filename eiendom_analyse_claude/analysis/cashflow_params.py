"""
Dataklasser for kontantstrømsanalyse – ingen tunge avhengigheter.
Importeres av både cashflow.py og excel_export.py.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class CashflowParams:
    """Alle parametere for kontantstrømsberegning."""

    # Finansiering
    equity: float = 500_000
    interest_rate: float = 0.055
    loan_years: int = 25
    interest_only: bool = False

    # Driftskostnader (NOK/år)
    insurance: float = 3_000
    tax: float = 0
    maintenance_pct_rent: float = 0.05

    # Strøm
    kwh_per_m2: float = 150
    electricity_price: float = 0.85
    tenant_pays_electricity: bool = True
    energy_factor: list[float] = field(
        default_factory=lambda: [0.7, 0.8, 0.9, 1.0, 1.1, 1.2, 1.35]
    )

    # Tomgang
    vacancy_months: float = 1.0

    # Fallback leie
    default_rent_per_m2: float = 150


@dataclass
class CashflowResult:
    """Resultat for én eiendom."""

    finnkode: str
    sales_price: float
    area: float
    estimated_rent_monthly: float
    energy_label: Optional[str]

    gross_rent_year: float
    interest_year: float
    principal_year: float
    insurance_year: float
    tax_year: float
    maintenance_year: float
    electricity_year: float
    common_cost_year: float
    kommunale_avgifter_year: float

    netto_cashflow_year: float
    gross_yield_pct: float
    net_yield_pct: float
    roi_pct: float
