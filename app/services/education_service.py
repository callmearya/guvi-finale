from __future__ import annotations

import json
from functools import lru_cache
from typing import Dict, List, Optional

from app.config import get_settings


@lru_cache()
def _load_json(path) -> List[Dict]:
    if not path.exists():
        return []
    data = json.loads(path.read_text())
    if isinstance(data, list):
        return data
    return []


class KnowledgeBaseService:
    def __init__(self) -> None:
        self.settings = get_settings()

    def schemes(self, language: str = "en") -> List[Dict[str, str]]:
        entries = _load_json(self.settings.schemes_path)
        normalized: List[Dict[str, str]] = []
        for item in entries:
            description = item.get("languages", {}).get(language) or item.get(
                "languages", {}
            ).get(self.settings.fallback_language) or item.get("description", "")
            normalized.append(
                {
                    "scheme": item.get("scheme"),
                    "ministry": item.get("ministry"),
                    "summary": description,
                    "how_to_apply": item.get("how_to_apply"),
                    "official_url": item.get("official_url"),
                }
            )
        return normalized

    def cooperatives(self, state: Optional[str]) -> List[Dict[str, str]]:
        entries = _load_json(self.settings.cooperatives_path)
        if not state:
            return entries
        state_lower = state.lower()
        return [item for item in entries if item.get("state", "").lower() == state_lower]

    def post_harvest(self, commodity: str) -> List[str]:
        entries = _load_json(self.settings.post_harvest_path)
        commodity_lower = commodity.lower()
        for item in entries:
            if item.get("commodity", "").lower() == commodity_lower:
                return item.get("recommendations", [])
        return []
