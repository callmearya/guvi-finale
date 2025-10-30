from __future__ import annotations

from typing import Dict, List, Optional

import requests

from app.config import get_settings
from app.utils.cache import JsonCache


class DataGovClient:
    """Thin wrapper around data.gov.in datasets with caching."""

    DAILY_PRICE_RESOURCE = "9ef84268-d588-465a-a308-a864a43d0070"
    MARKET_PROFILE_RESOURCE = "1f2cf7af-574e-4f43-8b82-cf3b40e17b36"

    def __init__(self) -> None:
        self.settings = get_settings()
        self.api_key = self.settings.gov_api_key
        self.enabled = bool(self.api_key)
        self.session = requests.Session()
        self.cache = JsonCache("data-gov", ttl_seconds=6 * 3600)

    def _request(self, resource_id: str, params: Optional[Dict[str, str]] = None, ttl: int = 3600) -> Optional[Dict]:
        if not self.enabled:
            return None
        params = params or {}
        params.setdefault("api-key", self.api_key)
        params.setdefault("format", "json")

        cache_key = f"{resource_id}_" + "_".join(f"{key}={value}" for key, value in sorted(params.items()))
        cached = self.cache.get(cache_key)
        if cached:
            return cached

        url = f"https://api.data.gov.in/resource/{resource_id}"
        try:
            response = self.session.get(url, params=params, timeout=30)
            response.raise_for_status()
            payload = response.json()
        except Exception:
            return None

        if payload.get("status") == "error":
            return None

        self.cache.set(cache_key, payload, override_ttl=ttl)
        return payload

    def get_market_directory(self) -> List[Dict[str, str]]:
        """Placeholder for compatibility; returns empty when resource not available."""
        return []

    def _sample_daily_data(self, limit: int = 500) -> List[Dict[str, str]]:
        payload = self._request(
            self.DAILY_PRICE_RESOURCE,
            params={"limit": limit, "sort": "desc"},
            ttl=2 * 3600,
        )
        if not payload:
            return []
        return payload.get("records", [])

    def list_states(self) -> List[str]:
        if not self.enabled:
            return []
        cache_key = "states_all"
        cached = self.cache.get(cache_key)
        if cached:
            return cached
        states: set[str] = set()
        limit = 100
        for offset in range(0, 5000, limit):
            payload = self._request(
                self.DAILY_PRICE_RESOURCE,
                params={"limit": limit, "offset": offset},
                ttl=3600,
            )
            if not payload:
                break
            records = payload.get("records", [])
            if not records:
                break
            for record in records:
                state = record.get("state")
                if state:
                    states.add(state)
            if len(records) < limit:
                break
        states_list = sorted(states)
        if states_list:
            self.cache.set(cache_key, states_list, override_ttl=3600)
        return states_list

    def list_districts(self, state: str) -> List[str]:
        if not self.enabled:
            return []
        cache_key = f"districts_{state.lower()}"
        cached = self.cache.get(cache_key)
        if cached:
            return cached
        payload = self.fetch_daily_prices(commodity=None, state=state, limit=500)
        districts = sorted(
            {
                record.get("district")
                for record in payload
                if record.get("district") and record.get("state") == state
            }
        )
        if districts:
            self.cache.set(cache_key, districts, override_ttl=3600)
        return districts

    def list_markets(self, commodity: Optional[str] = None, state: Optional[str] = None) -> List[str]:
        params: Dict[str, str] = {"limit": 300, "sort": "desc"}
        if commodity:
            params["filters[commodity]"] = commodity
        if state:
            params["filters[state]"] = state
        payload = self._request(self.DAILY_PRICE_RESOURCE, params=params, ttl=1800)
        if not payload:
            return []
        records = payload.get("records", [])
        filtered = [
            record
            for record in records
            if record.get("market")
            and (not state or record.get("state") == state)
            and (not commodity or record.get("commodity") == commodity)
        ]
        markets = sorted({record.get("market") for record in filtered})
        return markets

    def list_commodities(self) -> List[str]:
        if not self.enabled:
            return []
        cache_key = "commodities_all"
        cached = self.cache.get(cache_key)
        if cached:
            return cached
        commodities: set[str] = set()
        limit = 100
        for offset in range(0, 5000, limit):
            payload = self._request(
                self.DAILY_PRICE_RESOURCE,
                params={"limit": limit, "offset": offset},
                ttl=3600,
            )
            if not payload:
                break
            records = payload.get("records", [])
            if not records:
                break
            for record in records:
                commodity = record.get("commodity")
                if commodity:
                    commodities.add(commodity)
            if len(records) < limit:
                break
        commodities_list = sorted(commodities)
        if commodities_list:
            self.cache.set(cache_key, commodities_list, override_ttl=3600)
        return commodities_list

    def fetch_daily_prices(
        self,
        commodity: Optional[str] = None,
        market: Optional[str] = None,
        state: Optional[str] = None,
        limit: int = 60,
    ) -> List[Dict[str, str]]:
        params: Dict[str, str] = {"limit": limit, "sort": "desc"}
        if commodity:
            params["filters[commodity]"] = commodity
        if market:
            params["filters[market]"] = market
        if state:
            params["filters[state]"] = state
        payload = self._request(self.DAILY_PRICE_RESOURCE, params=params, ttl=900)
        if not payload:
            return []
        records = payload.get("records", [])
        if state:
            records = [record for record in records if record.get("state") == state]
        if commodity:
            records = [record for record in records if record.get("commodity") == commodity]
        if market:
            records = [record for record in records if record.get("market") == market]
        return records
