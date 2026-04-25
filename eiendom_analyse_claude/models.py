from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Any, Optional
import math


def _nan() -> float:
    """Factory for NaN floats (dataclass-friendly)."""
    return float("nan")


@dataclass
class RealEstate:
    """
    En FINN-boligannonse (salg).

    Alle numeriske felt er `float` slik at NaN er mulig.
    Prisfelter er i NOK, arealfelter i m².
    """

    # Identitet
    finnkode: str
    url: str

    # Tittel / type
    title: Optional[str] = None
    property_type: Optional[str] = None   # Leilighet, Enebolig, etc.

    # Adresse / geolokasjon
    location: Optional[str] = None
    latitude: float = field(default_factory=_nan)
    longitude: float = field(default_factory=_nan)

    # Bygningsdata
    bedrooms: float = field(default_factory=_nan)
    rooms: float = field(default_factory=_nan)
    floor: float = field(default_factory=_nan)
    construction_year: float = field(default_factory=_nan)
    energy_label: Optional[str] = None

    # Areal (m²)
    area: float = field(default_factory=_nan)
    internal_area: float = field(default_factory=_nan)
    external_area: float = field(default_factory=_nan)
    balcony_area: float = field(default_factory=_nan)

    # Priser (NOK)
    asking_price: float = field(default_factory=_nan)
    total_price: float = field(default_factory=_nan)
    registration_charge: float = field(default_factory=_nan)
    joint_debt: float = field(default_factory=_nan)
    common_monthly_cost: float = field(default_factory=_nan)
    municipality_cost_year: float = field(default_factory=_nan)   # NOK/år
    collective_assets: float = field(default_factory=_nan)
    tax_value_formueverdi: float = field(default_factory=_nan)

    # Analyse
    neighbors: list[str] = field(default_factory=list)

    # ----------------------------------------------------------------
    def has_valid_coordinates(self) -> bool:
        return (not math.isnan(self.latitude)) and (not math.isnan(self.longitude))

    @property
    def price_per_m2(self) -> float:
        """total_price / area  (NaN om utilgjengelig)."""
        if math.isnan(self.total_price) or math.isnan(self.area) or self.area <= 0:
            return math.nan
        return self.total_price / self.area

    @property
    def asking_per_m2(self) -> float:
        """asking_price / area  (NaN om utilgjengelig)."""
        if math.isnan(self.asking_price) or math.isnan(self.area) or self.area <= 0:
            return math.nan
        return self.asking_price / self.area

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "RealEstate":
        nb = data.get("neighbors")
        if isinstance(nb, str):
            data["neighbors"] = [x for x in nb.split(",") if x]
        # Bakoverkompatibilitet: fjern ukjente felt
        known = {f.name for f in cls.__dataclass_fields__.values()}
        filtered = {k: v for k, v in data.items() if k in known}
        return cls(**filtered)


@dataclass
class RentalEstate:
    """En FINN-leieannonse."""

    finnkode: str
    url: str

    title: Optional[str] = None
    location: Optional[str] = None
    property_type: Optional[str] = None

    # GPS
    latitude: float = field(default_factory=_nan)
    longitude: float = field(default_factory=_nan)

    # Utleie (NOK)
    monthly_rent: float = field(default_factory=_nan)
    deposit: float = field(default_factory=_nan)

    # Nøkkelinfo
    primary_area: float = field(default_factory=_nan)
    bedrooms: float = field(default_factory=_nan)
    floor: float = field(default_factory=_nan)

    lease_period: Optional[str] = None

    # ----------------------------------------------------------------
    def has_valid_coordinates(self) -> bool:
        return (not math.isnan(self.latitude)) and (not math.isnan(self.longitude))

    @property
    def rent_per_m2(self) -> float:
        if math.isnan(self.monthly_rent) or math.isnan(self.primary_area) or self.primary_area <= 0:
            return math.nan
        return self.monthly_rent / self.primary_area

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "RentalEstate":
        known = {f.name for f in cls.__dataclass_fields__.values()}
        filtered = {k: v for k, v in data.items() if k in known}
        return cls(**filtered)
