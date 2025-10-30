from fastapi import FastAPI, HTTPException

from app.models.schemas import RecommendationRequest, RecommendationResponse
from app.services.education_service import KnowledgeBaseService
from app.services.recommendation import FarmerAdvisor


app = FastAPI(
    title="Farmer Negotiation Assistant",
    description="Conversational AI backend to support Indian farmers with mandi price insights.",
    version="0.1.0",
)

advisor = FarmerAdvisor()
knowledge = KnowledgeBaseService()


@app.get("/health")
def health_check() -> dict:
    return {"status": "ok"}


@app.post("/recommendation", response_model=RecommendationResponse)
def create_recommendation(payload: RecommendationRequest) -> RecommendationResponse:
    try:
        return advisor.recommend(payload)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.get("/schemes")
def list_schemes(language: str = "en") -> dict:
    schemes = knowledge.schemes(language)
    return {"schemes": schemes}


@app.get("/cooperatives")
def list_cooperatives(state: str | None = None) -> dict:
    cooperatives = knowledge.cooperatives(state)
    return {"cooperatives": cooperatives}
