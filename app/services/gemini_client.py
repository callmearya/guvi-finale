from __future__ import annotations

from typing import Dict, Optional

from app.config import get_settings


class GeminiClient:
    """Thin wrapper around Google Gemini 2.5 Flash Lite with graceful fallback."""

    def __init__(self, model_name: str = "gemini-2.5-flash-lite") -> None:
        self.settings = get_settings()
        self.model_name = model_name
        self._model = None

    def _ensure_model(self) -> None:
        if self._model or not self.settings.gemini_api_key:
            return
        try:
            import google.generativeai as genai  # type: ignore

            genai.configure(api_key=self.settings.gemini_api_key)
            self._model = genai.GenerativeModel(self.model_name)
        except Exception:
            self._model = None

    @property
    def available(self) -> bool:
        self._ensure_model()
        return self._model is not None

    def generate(self, prompt: str, **kwargs) -> Optional[str]:
        self._ensure_model()
        if not self._model:
            return None
        try:
            response = self._model.generate_content(prompt, **kwargs)
            if hasattr(response, "text"):
                return response.text
            return str(response)
        except Exception:
            return None

    def structure_recommendation(self, payload: Dict) -> Dict:
        """Optionally ask Gemini to polish reasoning."""
        prompt = (
            "You are assisting Indian farmers. Convert the JSON summary into a friendly paragraph "
            "with bullet highlights in the specified language. Maintain numeric values as-is."
        )
        text = self.generate(f"{prompt}\n\n{payload}")
        if not text:
            return {"message": None}
        return {"message": text}
