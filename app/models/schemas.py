from __future__ import annotations

from typing import List, Optional, Tuple

from pydantic import BaseModel, Field, field_validator


class RecommendationRequest(BaseModel):
    commodity: str = Field(..., description="Commodity name e.g. Onion")
    market: str = Field(..., description="Target mandi/apmc name")
    quantity_qtl: float = Field(10.0, description="Quantity in quintals")
    district: Optional[str] = Field(None, description="Farmer district")
    state: Optional[str] = Field(None, description="Farmer state")
    farmer_coordinates: Optional[Tuple[float, float]] = Field(
        None, description="Latitude, Longitude tuple"
    )
    preferred_language: str = Field("en", description="ISO 639-1 language code")
    include_schemes: bool = Field(True)
    include_post_harvest: bool = Field(True)
    horizon_days: int = Field(14, gt=0, le=45)

    @field_validator("commodity", "market")
    @classmethod
    def _trim(cls, value: str) -> str:
        return value.strip()


class RecommendationPoint(BaseModel):
    label: str
    value: str
    detail: str


class RecommendationResponse(BaseModel):
    recommended_modal_price: float
    recommended_net_price: float
    currency: str = "INR"
    mandi: str
    commodity: str
    snapshot: List[RecommendationPoint]
    forecast: dict
    transport: dict
    supply_demand: dict
    reasoning: List[str]
    warnings: List[str] = Field(default_factory=list)
    schemes: List[dict] = Field(default_factory=list)
    cooperatives: List[dict] = Field(default_factory=list)
    post_harvest: List[str] = Field(default_factory=list)
    translated_summary: Optional[str] = None
