from __future__ import annotations

import math
from typing import Dict, List, Optional

import numpy as np
import pandas as pd
from statsmodels.tsa.statespace.sarimax import SARIMAX

from app.services.data_provider import MandiDataProvider
from app.utils.cache import JsonCache


class ArimaForecastService:
    def __init__(self, provider: MandiDataProvider) -> None:
        self.provider = provider
        self.cache = JsonCache("forecast", ttl_seconds=12 * 3600)

    @staticmethod
    def _safe_float(value: Optional[float]) -> Optional[float]:
        try:
            numeric = float(value)
        except (TypeError, ValueError):
            return None
        if math.isfinite(numeric):
            return numeric
        return None

    def _baseline_forecast(
        self,
        series: pd.Series,
        horizon_months: int,
        fallback_price: Optional[float] = None,
        fallback_start: Optional[pd.Timestamp] = None,
    ) -> Dict[str, List[Dict[str, Optional[float]]]]:
        rolling = series.tail(6)

        def _build_points(base_price: float, anchor: pd.Timestamp, steps: int) -> List[Dict[str, Optional[float]]]:
            points: List[Dict[str, Optional[float]]] = []
            for i in range(steps):
                forecast_date = (anchor + pd.DateOffset(months=i + 1)).date()
                price = round(float(base_price), 2)
                points.append(
                    {
                        "date": forecast_date.isoformat(),
                        "price": price,
                        "low": round(price * 0.9, 2),
                        "high": round(price * 1.1, 2),
                    }
                )
            return points

        steps = max(2, horizon_months)
        anchor = rolling.index[-1] if not rolling.empty else fallback_start or pd.Timestamp.today()

        if rolling.empty or pd.isna(rolling.mean()):
            base_price = self._safe_float(fallback_price)
            if base_price is None:
                base_price = self._safe_float(series.iloc[-1] if not series.empty else None)
            if base_price is None:
                return {"method": "fallback_baseline", "points": []}
            forecasts = _build_points(base_price, pd.Timestamp(anchor), steps)
            return {"method": "fallback_baseline", "points": forecasts}

        mean = float(rolling.mean())
        forecasts = _build_points(mean, pd.Timestamp(anchor), steps)
        return {"method": "rolling_mean", "points": forecasts}

    def forecast(
        self,
        commodity: str,
        market: str,
        horizon_days: int = 30,
        state: Optional[str] = None,
    ) -> Dict:
        horizon_months = max(1, math.ceil(horizon_days / 30))
        state_key = (state or "").lower()
        cache_key = f"{commodity.lower()}_{market.lower()}_{state_key}_{horizon_months}"
        cached = self.cache.get(cache_key)
        if cached:
            return cached

        series = self.provider.get_monthly_price_series(commodity, market)
        fallback_price: Optional[float] = None
        fallback_start: Optional[pd.Timestamp] = None

        if not series.empty:
            fallback_price = self._safe_float(series.iloc[-1])
            fallback_start = series.index[-1]

        if fallback_price is None or fallback_start is None:
            history = self.provider.get_recent_price_points(commodity, market, state=state, days=120)
            if history:
                fallback_price = fallback_price or history[-1].modal_price
                fallback_start = fallback_start or pd.Timestamp(history[-1].date)

        if series.empty or len(series) < 24:
            result = self._baseline_forecast(series, horizon_months, fallback_price, fallback_start)
            self.cache.set(cache_key, result)
            return result

        try:
            model = SARIMAX(
                series,
                order=(1, 1, 1),
                seasonal_order=(0, 1, 1, 12),
                enforce_stationarity=False,
                enforce_invertibility=False,
            )
            fitted = model.fit(disp=False)
            forecast_res = fitted.get_forecast(steps=horizon_months)
            mean_series = forecast_res.predicted_mean
            conf_int = forecast_res.conf_int(alpha=0.2)  # 80% band

            points = []
            for idx, value in enumerate(mean_series):
                date = mean_series.index[idx].date().isoformat()
                low = conf_int.iloc[idx, 0]
                high = conf_int.iloc[idx, 1]
                points.append(
                    {
                        "date": date,
                        "price": round(float(value), 2) if math.isfinite(float(value)) else None,
                        "low": round(float(low), 2) if math.isfinite(float(low)) else None,
                        "high": round(float(high), 2) if math.isfinite(float(high)) else None,
                    }
                )

            result = {
                "method": "sarimax",
                "points": points,
                "aic": self._safe_float(fitted.aic),
                "bic": self._safe_float(fitted.bic),
                "sample_size": len(series),
            }
        except Exception:
            result = self._baseline_forecast(series, horizon_months, fallback_price, fallback_start)

        self.cache.set(cache_key, result)
        return result
