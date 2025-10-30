from __future__ import annotations

import json
import math
from functools import lru_cache
from pathlib import Path
from typing import Dict, List, Sequence, Set, Tuple

from app.config import DATA_DIR


INDIAN_STATES: List[str] = [
    "Andhra Pradesh",
    "Arunachal Pradesh",
    "Assam",
    "Bihar",
    "Chhattisgarh",
    "Goa",
    "Gujarat",
    "Haryana",
    "Himachal Pradesh",
    "Jharkhand",
    "Karnataka",
    "Kerala",
    "Madhya Pradesh",
    "Maharashtra",
    "Manipur",
    "Meghalaya",
    "Mizoram",
    "Nagaland",
    "Odisha",
    "Punjab",
    "Rajasthan",
    "Sikkim",
    "Tamil Nadu",
    "Telangana",
    "Tripura",
    "Uttar Pradesh",
    "Uttarakhand",
    "West Bengal",
    "Andaman and Nicobar Islands",
    "Chandigarh",
    "Dadra and Nagar Haveli and Daman and Diu",
    "Delhi",
    "Jammu and Kashmir",
    "Ladakh",
    "Lakshadweep",
    "Puducherry",
]

STATE_ALIASES: Dict[str, str] = {
    "chattisgarh": "Chhattisgarh",
    "uttrakhand": "Uttarakhand",
    "nct of delhi": "Delhi",
}

STATE_REMOTE_OVERRIDES: Dict[str, str] = {
    "Chhattisgarh": "Chattisgarh",
    "Uttarakhand": "Uttrakhand",
    "Delhi": "NCT of Delhi",
}


def normalise_state_name(name: str) -> str:
    key = (name or "").strip()
    if not key:
        return ""
    return STATE_ALIASES.get(key.lower(), key)


def state_for_remote(name: str) -> str:
    canonical = normalise_state_name(name)
    return STATE_REMOTE_OVERRIDES.get(canonical, canonical)


@lru_cache(maxsize=1)
def load_reference_districts() -> Dict[str, List[str]]:
    path = DATA_DIR / "reference" / "district_centroids.json"
    if not path.exists():
        return {}

    try:
        data = json.loads(path.read_text())
    except json.JSONDecodeError:
        return {}

    mapping: Dict[str, Set[str]] = {}
    for row in data:
        state = row.get("state")
        district = row.get("district")
        if not state or not district:
            continue
        canonical = normalise_state_name(state)
        mapping.setdefault(canonical, set()).add(district)

    return {state: sorted(list(districts)) for state, districts in mapping.items()}


def reference_states() -> List[str]:
    states = {normalise_state_name(item) for item in INDIAN_STATES}
    states.update(load_reference_districts().keys())
    return sorted(states)


def _coerce_coordinates(value: Sequence[float] | Tuple[float, float] | None) -> Tuple[float, float] | None:
    if value is None:
        return None
    try:
        lat, lon = value
    except (TypeError, ValueError):
        return None
    if lat is None or lon is None:
        return None
    return float(lat), float(lon)


def haversine_km(
    origin: Sequence[float] | Tuple[float, float],
    destination: Sequence[float] | Tuple[float, float],
) -> float:
    """Compute great-circle distance between two lat/lon pairs."""
    start = _coerce_coordinates(origin)
    end = _coerce_coordinates(destination)
    if not start or not end:
        return 0.0

    lat1, lon1 = start
    lat2, lon2 = end

    radius_km = 6371.0
    d_lat = math.radians(lat2 - lat1)
    d_lon = math.radians(lon2 - lon1)
    lat1_rad = math.radians(lat1)
    lat2_rad = math.radians(lat2)

    hav = math.sin(d_lat / 2) ** 2 + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(d_lon / 2) ** 2
    central_angle = 2 * math.atan2(math.sqrt(hav), math.sqrt(max(1 - hav, 0)))
    return radius_km * central_angle
