from __future__ import annotations

import json
import math
from dataclasses import asdict, is_dataclass
from pathlib import Path
from typing import Any, Dict, Type, TypeVar

from eiendom_analyse_claude.models import RealEstate, RentalEstate

T = TypeVar("T")


# ---------------------------------------------------------------------------
# Hjelpere
# ---------------------------------------------------------------------------

def _is_nan(x: Any) -> bool:
    try:
        return isinstance(x, float) and math.isnan(x)
    except Exception:
        return False


def _is_better(new_val: Any, old_val: Any) -> bool:
    """Returner True hvis new_val er et bedre/mer komplett felt enn old_val."""
    if new_val is None:
        return False
    if _is_nan(new_val):
        return False
    if isinstance(new_val, str) and new_val.strip() == "":
        return False
    if old_val is None:
        return True
    if _is_nan(old_val):
        return True
    if isinstance(old_val, str) and old_val.strip() == "":
        return True
    return False


def merge_objects(existing: T, incoming: T) -> T:
    """Fyll tomme felt i `existing` med verdier fra `incoming`."""
    ex = asdict(existing) if is_dataclass(existing) else dict(existing.__dict__)
    inc = asdict(incoming) if is_dataclass(incoming) else dict(incoming.__dict__)

    for k, new_val in inc.items():
        old_val = ex.get(k)
        if _is_better(new_val, old_val):
            setattr(existing, k, new_val)
    return existing


# ---------------------------------------------------------------------------
# Lagring / lasting
# ---------------------------------------------------------------------------

def _to_json_safe(val: Any) -> Any:
    """Konverter NaN til None for gyldig JSON."""
    if isinstance(val, float) and math.isnan(val):
        return None
    if isinstance(val, dict):
        return {k: _to_json_safe(v) for k, v in val.items()}
    if isinstance(val, list):
        return [_to_json_safe(v) for v in val]
    return val


def save_estates(path: str, estates: Dict[str, Any]) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    payload: dict = {}
    for k, v in estates.items():
        raw = v.to_dict() if hasattr(v, "to_dict") else v.__dict__
        payload[k] = _to_json_safe(raw)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)


def load_objects(path: str, model_cls: Type[T]) -> Dict[str, T]:
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    out: Dict[str, T] = {}
    for fk, d in data.items():
        # None -> NaN for float-felt
        for key, val in d.items():
            if val is None:
                d[key] = float("nan")
        if hasattr(model_cls, "from_dict"):
            out[str(fk)] = model_cls.from_dict(d)  # type: ignore
        else:
            out[str(fk)] = model_cls(**d)           # type: ignore
    return out


def load_estates(path: str) -> Dict[str, RealEstate]:
    return load_objects(path, RealEstate)


def load_rentals(path: str) -> Dict[str, RentalEstate]:
    return load_objects(path, RentalEstate)


def save_or_merge(path: str, incoming: Dict[str, T], model_cls: Type[T]) -> Dict[str, T]:
    """Last eksisterende data, merge ny data, og lagre."""
    existing: Dict[str, T] = {}
    if Path(path).exists():
        try:
            existing = load_objects(path, model_cls)
        except Exception as e:
            print(f"[store] Kunne ikke laste {path}: {e}")

    for fk, obj in incoming.items():
        fk = str(fk)
        if fk in existing:
            existing[fk] = merge_objects(existing[fk], obj)
        else:
            existing[fk] = obj

    save_estates(path, existing)
    return existing
