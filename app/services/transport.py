from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Dict, Optional, Tuple

from app.config import get_settings
from app.utils.geo import haversine_km


@lru_cache()
def _load_reference_data(path: Path) -> Dict[str, Dict]:
    if not path.exists():
        return {}
    data = json.loads(path.read_text())
    return {
        item["name"].lower(): item
        for item in data
    }


@lru_cache()
def _load_district_centroids(path: Path) -> Dict[str, Tuple[float, float]]:
    if not path.exists():
        return {}
    data = json.loads(path.read_text())
    mapping: Dict[str, Tuple[float, float]] = {}
    for item in data:
        key = f"{item['district'].lower()}|{item['state'].lower()}"
        mapping[key] = (item["latitude"], item["longitude"])
    return mapping


class TransportCostEstimator:
    """Approximates transport cost per quintal for mandi deliveries."""

    def __init__(self) -> None:
        settings = get_settings()
        self.market_map = _load_reference_data(settings.markets_config_path)
        self.district_centroids = _load_district_centroids(
            settings.markets_config_path.parent / "district_centroids.json"
        )

    def _get_origin_coordinates(
        self,
        district: Optional[str],
        state: Optional[str],
        fallback_coordinates: Optional[Tuple[float, float]],
    ) -> Optional[Tuple[float, float]]:
        if fallback_coordinates:
            return fallback_coordinates
        if not district or not state:
            return None
        key = f"{district.lower()}|{state.lower()}"
        return self.district_centroids.get(key)

    def estimate(
        self,
        market_name: str,
        quantity_qtl: float,
        district: Optional[str] = None,
        state: Optional[str] = None,
        farmer_coordinates: Optional[Tuple[float, float]] = None,
        vehicle_type: str = "truck",
    ) -> Dict[str, float]:
        market = self.market_map.get(market_name.lower())
        if not market:
            return {
                "total_cost": 0.0,
                "per_quintal_cost": 0.0,
                "distance_km": 0.0,
                "note": "market_not_in_reference",
            }

        origin = self._get_origin_coordinates(district, state, farmer_coordinates)
        if not origin:
            return {
                "total_cost": 0.0,
                "per_quintal_cost": 0.0,
                "distance_km": 0.0,
                "note": "origin_location_missing",
            }

        destination = (market["latitude"], market["longitude"])
        distance_km = haversine_km(origin, destination)

        rate_per_km = market.get("truck_rate_per_km", 6.5)
        if vehicle_type == "mini_truck":
            rate_per_km *= 0.75
        elif vehicle_type == "tractor":
            rate_per_km *= 0.6

        base_cost = distance_km * rate_per_km
        handling_markup = 1 + market.get("last_mile_markup", 0.1)
        subtotal = base_cost * handling_markup
        quantity_qtl = max(quantity_qtl, 1)
        per_quintal_cost = subtotal / quantity_qtl
        return {
            "total_cost": round(subtotal, 2),
            "per_quintal_cost": round(per_quintal_cost, 2),
            "distance_km": round(distance_km, 1),
            "rate_per_km": round(rate_per_km, 2),
            "note": "estimated_using_reference_rates",
        }
