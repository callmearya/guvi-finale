from __future__ import annotations

import statistics
from typing import List

from app.models.schemas import RecommendationRequest, RecommendationResponse, RecommendationPoint
from app.services.data_provider import MandiDataProvider
from app.services.education_service import KnowledgeBaseService
from app.services.forecast import ArimaForecastService
from app.services.gemini_client import GeminiClient
from app.services.localization import LocalizationService
from app.services.transport import TransportCostEstimator


class FarmerAdvisor:
    def __init__(self) -> None:
        self.provider = MandiDataProvider()
        self.forecaster = ArimaForecastService(self.provider)
        self.knowledge = KnowledgeBaseService()
        self.transport = TransportCostEstimator()
        self.localization = LocalizationService()
        self.gemini = GeminiClient()

    def _build_snapshot(self, history) -> List[RecommendationPoint]:
        latest = history[-1]
        avg_week = statistics.mean(point.modal_price for point in history[-7:]) if len(history) >= 7 else latest.modal_price
        avg_month = statistics.mean(point.modal_price for point in history[-30:]) if len(history) >= 30 else avg_week
        return [
            RecommendationPoint(
                label="Latest modal price",
                value=f"₹{latest.modal_price:.0f}/qtl",
                detail=f"Recorded on {latest.date.isoformat()} with arrivals {latest.arrivals_in_qtl:.0f} qtl",
            ),
            RecommendationPoint(
                label="7-day average",
                value=f"₹{avg_week:.0f}/qtl",
                detail="Average of past week observations",
            ),
            RecommendationPoint(
                label="30-day average",
                value=f"₹{avg_month:.0f}/qtl",
                detail="Average of past month observations",
            ),
        ]

    def recommend(self, request: RecommendationRequest) -> RecommendationResponse:
        history = self.provider.get_recent_price_points(
            request.commodity, request.market, state=request.state, days=120
        )
        if not history:
            raise ValueError("No price history available for the commodity-market pair.")

        snapshot = self._build_snapshot(history)
        latest_price = history[-1].modal_price
        weekly_avg = statistics.mean(point.modal_price for point in history[-7:]) if len(history) >= 7 else latest_price

        supply = self.provider.get_supply_demand_trend(request.commodity, request.market, state=request.state)
        forecast = self.forecaster.forecast(
            request.commodity,
            request.market,
            horizon_days=request.horizon_days,
            state=request.state,
        )

        transport = self.transport.estimate(
            market_name=request.market,
            quantity_qtl=request.quantity_qtl,
            district=request.district,
            state=request.state,
            farmer_coordinates=request.farmer_coordinates,
        )

        first_forecast = forecast["points"][0] if forecast["points"] else {"price": latest_price}
        trend_adjustment = (first_forecast["price"] - weekly_avg) * 0.4
        supply_penalty = -max(min(supply.get("supply_pressure", 0.0), 0.25), -0.25) * 0.2 * weekly_avg
        recommended_modal = latest_price + trend_adjustment + supply_penalty
        recommended_modal = max(recommended_modal, latest_price * 0.9)
        recommended_modal = min(recommended_modal, latest_price * 1.15)

        net_price = recommended_modal - transport.get("per_quintal_cost", 0.0)

        reasoning: List[str] = []
        reasoning.append(
            f"Latest mandi modal price is ₹{latest_price:.0f}/qtl with arrivals {history[-1].arrivals_in_qtl:.0f} qtl."
        )
        reasoning.append(
            f"ARIMA forecast for next month suggests ₹{first_forecast['price']:.0f}/qtl."
        )
        if supply.get("supply_pressure") is not None:
            reasoning.append(
                f"Supply pressure indicator at {supply['supply_pressure']:.2f} adjusts negotiation band."
            )
        if transport.get("per_quintal_cost"):
            reasoning.append(
                f"Estimated transport cost is ₹{transport['per_quintal_cost']:.0f}/qtl over {transport['distance_km']:.0f} km."
            )

        warnings: List[str] = []
        if latest_price < weekly_avg * 0.9:
            warnings.append(
                "Current modal price is >10% below weekly average. Verify mandi deductions to avoid distress sale."
            )
        if supply.get("supply_pressure", 0) > 0.25:
            warnings.append(
                "High arrivals indicate oversupply. Consider staggered dispatch or nearby markets."
            )

        schemes = self.knowledge.schemes(request.preferred_language) if request.include_schemes else []
        cooperatives = self.knowledge.cooperatives(request.state) if request.include_schemes else []
        post_harvest = self.knowledge.post_harvest(request.commodity) if request.include_post_harvest else []

        translated_summary = None
        if request.preferred_language and request.preferred_language != "en":
            base_text = (
                f"Negotiate around ₹{recommended_modal:.0f} per quintal at {request.market}. "
                f"After subtracting transport, expected net is ₹{net_price:.0f}. "
                + " ".join(reasoning)
            )
            translated_summary = self.localization.translate(base_text, request.preferred_language)

        response = RecommendationResponse(
            recommended_modal_price=round(recommended_modal, 2),
            recommended_net_price=round(net_price, 2),
            mandi=request.market,
            commodity=request.commodity,
            snapshot=snapshot,
            forecast=forecast,
            transport=transport,
            supply_demand=supply,
            reasoning=reasoning,
            warnings=warnings,
            schemes=schemes,
            cooperatives=cooperatives,
            post_harvest=post_harvest,
            translated_summary=translated_summary,
        )

        if self.gemini.available and translated_summary:
            polished = self.gemini.structure_recommendation(
                {
                    "commodity": request.commodity,
                    "market": request.market,
                    "recommended_modal_price": recommended_modal,
                    "reasoning": reasoning,
                    "warnings": warnings,
                    "language": request.preferred_language,
                }
            )
            if polished.get("message"):
                response.translated_summary = polished["message"]

        return response
