from __future__ import annotations

import numpy as np
from sklearn.neighbors import BallTree

EARTH_RADIUS_M = 6_371_000.0


def build_balltree(latitudes: np.ndarray, longitudes: np.ndarray) -> BallTree:
    coords_rad = np.radians(np.c_[latitudes, longitudes])
    return BallTree(coords_rad, metric="haversine")


def query_neighbors_indices(
    tree: BallTree,
    latitudes: np.ndarray,
    longitudes: np.ndarray,
    radius_m: float,
) -> list[np.ndarray]:
    coords_rad = np.radians(np.c_[latitudes, longitudes])
    radius_rad = float(radius_m) / EARTH_RADIUS_M
    return tree.query_radius(coords_rad, r=radius_rad)
