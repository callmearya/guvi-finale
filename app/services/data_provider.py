from __future__ import annotations

import datetime as dt
import json
from dataclasses import dataclass
from typing import Dict, List, Optional

import pandas as pd

from app.config import RAW_DATA_PATH, get_settings
from app.services.data_gov_client import DataGovClient
from app.utils.cache import JsonCache
from app.utils.geo import (
    load_reference_districts,
    normalise_state_name,
    reference_states,
    state_for_remote,
)


@dataclass
class PricePoint:
    date: dt.date
    min_price: float
    max_price: float
    modal_price: float
    arrivals_in_qtl: float


class MandiDataProvider:
    """Loads mandi price data with online + offline fallbacks."""

    def __init__(self) -> None:
        self.settings = get_settings()
        self.cache = JsonCache("mandi-data", ttl_seconds=self.settings.cache_ttl_minutes * 60)
        self._dataframe: Optional[pd.DataFrame] = None
        self.gov_client = DataGovClient()

    def _load_local_dataset(self) -> pd.DataFrame:
        if self._dataframe is not None:
            return self._dataframe

        df = pd.read_csv(RAW_DATA_PATH)
        df["date"] = pd.to_datetime(df["date"])
        df["modal_price"] = pd.to_numeric(df["modal_price"], errors="coerce")
        df["min_price"] = pd.to_numeric(df["min_price"], errors="coerce")
        df["max_price"] = pd.to_numeric(df["max_price"], errors="coerce")
        df["arrivals_in_qtl"] = pd.to_numeric(df["arrivals_in_qtl"], errors="coerce")
        df["commodity_lower"] = df["Commodity"].str.strip().str.lower()
        df["market_lower"] = df["APMC"].str.strip().str.lower()
        self._dataframe = df.dropna(subset=["modal_price", "date"])
        return self._dataframe

    def _fetch_remote_records(
        self, commodity: str, market: str, state: Optional[str] = None, limit: int = 60
    ) -> Optional[List[Dict]]:
        if not self.gov_client.enabled:
            return None

        cache_key = f"gov_records_{commodity}_{market}_{state}"
        cached = self.cache.get(cache_key)
        if cached:
            return cached

        records = self.gov_client.fetch_daily_prices(
            commodity=commodity,
            market=market,
            state=state,
            limit=limit,
        )
        if not records:
            return None

        self.cache.set(cache_key, records, override_ttl=1800)
        return records

    def get_recent_price_points(
        self,
        commodity: str,
        market: str,
        state: Optional[str] = None,
        days: int = 45,
    ) -> List[PricePoint]:
        commodity_lower = commodity.strip().lower()
        market_lower = market.strip().lower()

        df = self._load_local_dataset()
        since = pd.Timestamp.today() - pd.Timedelta(days=days)
        filtered = df[
            (df["commodity_lower"] == commodity_lower)
            & (df["market_lower"] == market_lower)
            & (df["date"] >= since)
        ].sort_values("date")

        if filtered.empty:
            fallback = df[
                (df["commodity_lower"] == commodity_lower)
                & (df["market_lower"] == market_lower)
            ].sort_values("date").tail(max(30, days // 3))
            if fallback.empty:
                records = self._fetch_remote_records(commodity, market, state=state)
                if not records:
                    return []
                points: List[PricePoint] = []
                for record in records:
                    try:
                        price = float(record.get("modal_price", 0))
                    except (TypeError, ValueError):
                        continue
                    try:
                        arrival_date = pd.to_datetime(
                            record.get("arrival_date"), dayfirst=True, errors="coerce"
                        )
                        if pd.isna(arrival_date):
                            continue
                        point = PricePoint(
                            date=arrival_date.date(),
                            min_price=float(record.get("min_price", 0) or 0),
                            max_price=float(record.get("max_price", 0) or 0),
                            modal_price=price,
                            arrivals_in_qtl=float(record.get("arrivals_in_qtl", 0) or 0),
                        )
                        points.append(point)
                    except Exception:
                        continue
                return sorted(points, key=lambda x: x.date)
            filtered = fallback
        else:
            # augment with live records to extend to present
            live_records = self._fetch_remote_records(commodity, market, state=state)
            if live_records:
                points: Dict[dt.date, PricePoint] = {
                    row["date"].date(): PricePoint(
                        date=row["date"].date(),
                        min_price=float(row["min_price"]),
                        max_price=float(row["max_price"]),
                        modal_price=float(row["modal_price"]),
                        arrivals_in_qtl=float(row["arrivals_in_qtl"]),
                    )
                    for _, row in filtered.iterrows()
                }
                for record in live_records:
                    try:
                        arrival_date = pd.to_datetime(
                            record.get("arrival_date"), dayfirst=True, errors="coerce"
                        )
                        if pd.isna(arrival_date):
                            continue
                        parsed_date = arrival_date.date()
                        points[parsed_date] = PricePoint(
                            date=parsed_date,
                            min_price=float(record.get("min_price") or 0),
                            max_price=float(record.get("max_price") or 0),
                            modal_price=float(record.get("modal_price") or 0),
                            arrivals_in_qtl=float(record.get("arrivals_in_qtl") or 0),
                        )
                    except Exception:
                        continue
                return sorted(points.values(), key=lambda x: x.date)

        return [
            PricePoint(
                date=row["date"].date(),
                min_price=float(row["min_price"]),
                max_price=float(row["max_price"]),
                modal_price=float(row["modal_price"]),
                arrivals_in_qtl=float(row["arrivals_in_qtl"]),
            )
            for _, row in filtered.iterrows()
        ]

    def get_supply_demand_trend(
        self, commodity: str, market: str, window_days: int = 90, state: Optional[str] = None
    ) -> Dict[str, float]:
        history = self.get_recent_price_points(commodity, market, state=state, days=window_days)
        if len(history) < 5:
            return {"trend": 0.0, "note": "insufficient data"}

        arrivals = pd.Series([point.arrivals_in_qtl for point in history])
        prices = pd.Series([point.modal_price for point in history])
        arrivals_change = (arrivals.iloc[-1] - arrivals.mean()) / max(arrivals.mean(), 1)
        price_change = (prices.iloc[-1] - prices.mean()) / max(prices.mean(), 1)
        return {
            "trend": float(price_change),
            "supply_pressure": float(arrivals_change),
            "latest_arrivals": float(arrivals.iloc[-1]),
            "latest_price": float(prices.iloc[-1]),
        }

    def get_monthly_price_series(
        self,
        commodity: str,
        market: str,
        max_years: int = 8,
    ) -> pd.Series:
        df = self._load_local_dataset()
        commodity_lower = commodity.strip().lower()
        market_lower = market.strip().lower()

        end_date = pd.Timestamp.today()
        start_date = end_date - pd.DateOffset(years=max_years)
        subset = df[
            (df["commodity_lower"] == commodity_lower)
            & (df["market_lower"] == market_lower)
            & (df["date"] >= start_date)
        ]
        if subset.empty:
            subset = df[
                (df["commodity_lower"] == commodity_lower)
                & (df["market_lower"] == market_lower)
            ].sort_values("date").tail(max_years * 12)
            if subset.empty:
                return pd.Series(dtype=float)

        subset = subset.set_index("date").sort_index()
        ts = subset["modal_price"].resample("MS").mean().dropna()
        return ts

    def get_available_markets(self) -> List[str]:
        df = self._load_local_dataset()
        markets = set(df["APMC"].dropna().unique().tolist())
        if self.gov_client.enabled:
            live_markets = self.gov_client.list_markets()
            markets.update(live_markets)
        return sorted(markets)

    def list_states(self) -> List[str]:
        collected: set[str] = set()
        if self.gov_client.enabled:
            states = self.gov_client.list_states()
            if states:
                collected.update(normalise_state_name(item) for item in states)
        collected.update(reference_states())
        df = self._load_local_dataset()
        if "state_name" in df.columns:
            collected.update(
                normalise_state_name(item)
                for item in df["state_name"].dropna().unique().tolist()
            )
        return sorted(state for state in collected if state)

    def list_districts(self, state: str) -> List[str]:
        canonical = normalise_state_name(state)
        if self.gov_client.enabled:
            target = state_for_remote(state)
            districts = self.gov_client.list_districts(target)
            if districts:
                return districts
        df = self._load_local_dataset()
        if "state_name" in df.columns and "district_name" in df.columns:
            subset = df[df["state_name"].str.lower() == canonical.lower()]
            districts = sorted(subset["district_name"].dropna().unique().tolist())
            if districts:
                return districts
        reference_mapping = load_reference_districts()
        for key, values in reference_mapping.items():
            if normalise_state_name(key).lower() == canonical.lower():
                return values
        return []

    def list_commodities(self) -> List[str]:
        if self.gov_client.enabled:
            commodities = self.gov_client.list_commodities()
            if commodities:
                return commodities
        df = self._load_local_dataset()
        return sorted(df["Commodity"].dropna().unique().tolist())

    def snapshot_to_dict(self, points: List[PricePoint]) -> List[Dict[str, str]]:
        return [
            {
                "date": point.date.isoformat(),
                "modal_price": round(point.modal_price, 2),
                "min_price": round(point.min_price, 2),
                "max_price": round(point.max_price, 2),
                "arrivals_in_qtl": round(point.arrivals_in_qtl, 2),
            }
            for point in points
        ]
