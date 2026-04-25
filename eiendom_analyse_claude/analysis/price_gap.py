"""
Nabobasert prisanalyse (price gap).

Beregner for hvert objekt:
- own_ppm2         : egen pris per m²
- neighbor_avg_ppm2: gjennomsnitts-ppm2 for naboer innen radius
- gap_ppm2         : neighbor_avg - own  (positivt = relativt billig)
- gap_pct          : gap som prosent av neighbor_avg
"""
from __future__ import annotations

import math
import numpy as np
import pandas as pd
from sklearn.neighbors import BallTree

EARTH_RADIUS_M = 6_371_000.0


def compute_price_gaps(
    df: pd.DataFrame,
    radius_m: float = 500,
    price_field: str = "total_price",
    min_neighbors: int = 5,
) -> pd.DataFrame:
    """
    Beregn prisavvik per objekt.

    Parametere
    ----------
    df : DataFrame
        Må inneholde kolonnene: latitude, longitude, area, og `price_field`.
    radius_m : float
        Søkeradius i meter.
    price_field : str
        Priskolonne ('total_price' eller 'asking_price').
    min_neighbors : int
        Minimum antall naboer for at gap skal beregnes.

    Returnerer
    ----------
    df med nye kolonner: own_ppm2, neighbor_avg_ppm2, neighbor_count, gap_ppm2, gap_pct
    """
    df_geo = df[df["latitude"].notna() & df["longitude"].notna()].copy()

    if df_geo.empty:
        return df_geo

    coords_rad = np.radians(df_geo[["latitude", "longitude"]].values)
    tree = BallTree(coords_rad, metric="haversine")
    radius_rad = float(radius_m) / EARTH_RADIUS_M
    neighbor_indices = tree.query_radius(coords_rad, r=radius_rad)

    df_geo["own_ppm2"] = df_geo[price_field] / df_geo["area"]

    neighbor_avgs, counts, gaps, gap_pcts = [], [], [], []

    for i, idxs in enumerate(neighbor_indices):
        idxs = idxs[idxs != i]

        ppm2_list = []
        for j in idxs:
            nb_area = df_geo.iloc[j]["area"]
            nb_price = df_geo.iloc[j][price_field]
            if pd.notna(nb_area) and pd.notna(nb_price) and nb_area > 0 and nb_price > 0:
                ppm2_list.append(float(nb_price) / float(nb_area))

        counts.append(len(ppm2_list))

        if len(ppm2_list) < min_neighbors:
            neighbor_avgs.append(np.nan)
            gaps.append(np.nan)
            gap_pcts.append(np.nan)
            continue

        avg = float(np.mean(ppm2_list))
        own = float(df_geo.iloc[i]["own_ppm2"])
        gap = avg - own
        neighbor_avgs.append(avg)
        gaps.append(gap)
        gap_pcts.append((gap / avg * 100) if avg > 0 else np.nan)

    df_geo["neighbor_avg_ppm2"] = neighbor_avgs
    df_geo["neighbor_count"] = counts
    df_geo["gap_ppm2"] = gaps
    df_geo["gap_pct"] = gap_pcts

    return df_geo
