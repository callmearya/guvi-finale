from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Dict, List

import pandas as pd

from flask import Blueprint, jsonify, render_template, request
from sqlalchemy.exc import SQLAlchemyError

from app.config import get_settings
from app.db import SessionLocal
from app.models.db_models import QueryLog
from app.models.schemas import RecommendationRequest
from app.services.localization import LocalizationService
from app.services.recommendation import FarmerAdvisor


settings = get_settings()
advisor = FarmerAdvisor()
provider = advisor.provider
localizer = LocalizationService()

resource_catalog_path = Path("data/reference/resource_ids.json")
if resource_catalog_path.exists():
    RESOURCE_CATALOG: List[Dict] = json.loads(resource_catalog_path.read_text())
else:
    RESOURCE_CATALOG = []


def _build_commodity_options() -> List[str]:
    options = provider.list_commodities()
    if options:
        return options
    dataset = provider._load_local_dataset()
    return sorted(dataset["Commodity"].dropna().unique().tolist())


def _build_state_options() -> List[str]:
    options = provider.list_states()
    if options:
        return options
    dataset = provider._load_local_dataset()
    return sorted(dataset["state_name"].dropna().unique().tolist())


def _build_commodity_market_map(commodities: List[str]) -> Dict[str, List[str]]:
    mapping: Dict[str, List[str]] = {}
    for commodity in commodities[:40]:
        markets = provider.gov_client.list_markets(commodity=commodity) if provider.gov_client.enabled else []
        if not markets:
            dataset = provider._load_local_dataset()
            subset = dataset[dataset["Commodity"].str.lower() == commodity.lower()]
            markets = sorted(subset["APMC"].dropna().unique().tolist())
        mapping[commodity] = markets[:80]
    return mapping


def _build_state_district_map(states: List[str]) -> Dict[str, List[str]]:
    mapping: Dict[str, List[str]] = {}
    for state in states:
        districts = provider.list_districts(state)
        mapping[state] = districts
    return mapping


COMMODITY_OPTIONS = _build_commodity_options()
STATE_OPTIONS = _build_state_options()
commodity_market_map = _build_commodity_market_map(COMMODITY_OPTIONS)
state_district_map = _build_state_district_map(STATE_OPTIONS)


web_bp = Blueprint("web", __name__)
api_bp = Blueprint("api", __name__)


@web_bp.route("/")
def index():
    return render_template(
        "index.html",
        resource_catalog=RESOURCE_CATALOG,
        default_language=settings.fallback_language,
        commodity_options=COMMODITY_OPTIONS,
        commodity_market_map=commodity_market_map,
        state_options=STATE_OPTIONS,
        state_district_map=state_district_map,
    )


@api_bp.route("/resource-ids")
def list_resource_ids():
    return jsonify({"resources": RESOURCE_CATALOG})


@api_bp.route("/translate", methods=["POST"])
def translate_texts():
    payload = request.get_json() or {}
    texts = payload.get("texts", [])
    language = payload.get("language", settings.fallback_language)
    if not isinstance(texts, list):
        return jsonify({"error": "Invalid payload"}), 400
    translations = localizer.translate_many([str(text) for text in texts], language)
    return jsonify({"translations": translations})


@api_bp.route("/recommendation", methods=["POST"])
def make_recommendation():
    payload = request.get_json() or request.form.to_dict()
    if not payload:
        return jsonify({"error": "Missing request payload"}), 400

    try:
        req = RecommendationRequest(
            commodity=payload.get("commodity", "Onion"),
            market=payload.get("market", "Lasalgaon"),
            quantity_qtl=float(payload.get("quantity_qtl", payload.get("quantity", 10))),
            district=payload.get("district"),
            state=payload.get("state"),
            preferred_language=payload.get("preferred_language", settings.fallback_language),
            horizon_days=int(payload.get("horizon_days", settings.max_forecast_horizon_days)),
        )
    except Exception as exc:  # noqa: BLE001
        return jsonify({"error": f"Invalid request: {exc}"}), 400

    start_time = time.perf_counter()
    status = "success"
    warning = None
    response_body: Dict = {}

    try:
        recommendation = advisor.recommend(req)
        duration_ms = (time.perf_counter() - start_time) * 1000

        best_forecast = max(
            recommendation.forecast.get("points", []),
            key=lambda item: item.get("price", 0),
            default=None,
        )

        top_markets: List[Dict[str, str]] = []
        if provider.gov_client.enabled:
            records = provider.gov_client.fetch_daily_prices(
                commodity=req.commodity,
                state=req.state,
                limit=200,
            )
            if records:
                df_remote = (
                    pd.DataFrame(records)[["market", "modal_price"]]
                    .dropna()
                    .assign(modal_price=lambda d: pd.to_numeric(d["modal_price"], errors="coerce"))
                )
                df_remote = df_remote.dropna()
                stats = df_remote.groupby("market")["modal_price"].mean().nlargest(3)
                top_markets = [
                    {"market": market, "average_price": round(price, 2)}
                    for market, price in stats.items()
                ]

        if not top_markets:
            dataset = provider._load_local_dataset()
            commodity_lower = req.commodity.strip().lower()
            commodity_df = dataset[dataset["commodity_lower"] == commodity_lower]
            if not commodity_df.empty:
                market_stats = (
                    commodity_df.groupby("APMC")["modal_price"].mean().nlargest(3).round(2)
                )
                for market_name, avg_price in market_stats.items():
                    top_markets.append({"market": market_name, "average_price": float(avg_price)})

        response_body = {
            "recommended_modal_price": recommendation.recommended_modal_price,
            "recommended_net_price": recommendation.recommended_net_price,
            "mandi": recommendation.mandi,
            "commodity": recommendation.commodity,
            "reasoning": recommendation.reasoning,
            "warnings": recommendation.warnings,
            "schemes": recommendation.schemes,
            "cooperatives": recommendation.cooperatives,
            "post_harvest": recommendation.post_harvest,
            "snapshot": [item.model_dump() for item in recommendation.snapshot],
            "forecast": recommendation.forecast,
            "transport": recommendation.transport,
            "supply_demand": recommendation.supply_demand,
            "translated_summary": recommendation.translated_summary,
            "best_sale_window": best_forecast,
            "top_markets": top_markets,
            "duration_ms": round(duration_ms, 2),
        }

    except Exception as exc:  # noqa: BLE001
        status = "error"
        warning = str(exc)
        duration_ms = (time.perf_counter() - start_time) * 1000
        response_body = {"error": warning}

    try:
        session = SessionLocal()
    except Exception:
        session = None

    if session is not None:
        try:
            log_entry = QueryLog(
                commodity=req.commodity,
                market=req.market,
                language=req.preferred_language,
                quantity_qtl=req.quantity_qtl,
                duration_ms=duration_ms,
                status=status,
                warning=warning,
                response=response_body if status == "error" else None,
            )
            session.add(log_entry)
            session.commit()
        except SQLAlchemyError:
            session.rollback()
        except Exception:
            pass
        finally:
            session.close()

    http_code = 200 if status == "success" else 500
    return jsonify(response_body), http_code
