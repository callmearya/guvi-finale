"""Utility to prewarm cache files for low-connectivity deployments."""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.services.recommendation import FarmerAdvisor
from app.models.schemas import RecommendationRequest


PAIRINGS = [
    {"commodity": "Onion", "market": "Lasalgaon", "district": "Nashik", "state": "Maharashtra"},
    {"commodity": "Tomato", "market": "Pune", "district": "Pune", "state": "Maharashtra"},
    {"commodity": "Grapes", "market": "Vashi", "district": "Nashik", "state": "Maharashtra"},
]


def main() -> None:
    advisor = FarmerAdvisor()
    for pair in PAIRINGS:
        request = RecommendationRequest(
            commodity=pair["commodity"],
            market=pair["market"],
            quantity_qtl=15,
            district=pair["district"],
            state=pair["state"],
            preferred_language="hi",
        )
        try:
            advisor.recommend(request)
            print(f"Cached recommendation for {pair['commodity']} at {pair['market']}")
        except Exception as exc:
            print(f"Failed to cache {pair['commodity']} at {pair['market']}: {exc}")


if __name__ == "__main__":
    main()
