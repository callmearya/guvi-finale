from __future__ import annotations

import re
from typing import Dict, List

from langdetect import detect, LangDetectException
import requests

from app.config import get_settings
from app.services.gemini_client import GeminiClient


FALLBACK_MAP: Dict[str, Dict[str, str]] = {
    "recommended_price": {
        "hi": "सुझाई गई मंडी कीमत",
        "mr": "शिफारस केलेली बाजारभाव",
    },
    "transport_cost": {
        "hi": "परिवहन लागत",
        "mr": "वाहतूक खर्च",
    },
    "supply_pressure": {
        "hi": "आपूर्ति दबाव",
        "mr": "पुरवठा दडपण",
    },
}


class LocalizationService:
    def __init__(self) -> None:
        self.settings = get_settings()
        self.gemini = GeminiClient()

    def detect_language(self, text: str) -> str:
        try:
            language = detect(text)
            return language
        except LangDetectException:
            return self.settings.default_language

    def translate(self, text: str, target_language: str) -> str:
        if target_language == "en":
            return text

        if self.gemini.available:
            prompt = (
                "Translate the following advisory for Indian farmers into {lang}. "
                "Use simple wording and keep measurements unchanged:\n\n{payload}"
            ).format(lang=target_language, payload=text)
            translated = self.gemini.generate(prompt)
            if translated:
                return translated

        if self.settings.libretranslate_url:
            try:
                payload = {
                    "q": text,
                    "source": "auto",
                    "target": target_language,
                    "format": "text",
                }
                response = requests.post(
                    self.settings.libretranslate_url,
                    json=payload,
                    headers={
                        "Content-Type": "application/json",
                        "Accept": "application/json",
                    },
                    timeout=15,
                )
                if response.status_code == 200:
                    data = response.json()
                    if isinstance(data, dict) and data.get("translatedText"):
                        return data["translatedText"]
            except Exception:
                pass

        templated = self._template_translate(text, target_language)
        if templated:
            return templated

        # Fallback: return original text if we cannot translate reliably
        return text

    def localize_label(self, label: str, language: str) -> str:
        localized = FALLBACK_MAP.get(label, {}).get(language)
        if localized:
            return localized
        return label.replace("_", " ").title()

    def translate_many(self, texts: List[str], target_language: str) -> List[str]:
        if target_language == "en":
            return texts
        results: List[str] = []
        for text in texts:
            if not text:
                results.append(text)
                continue
            results.append(self.translate(text, target_language))
        return results

    def _template_translate(self, text: str, language: str) -> str:
        language_templates = {
            "hi": {
                "negotiate": "{market} मंडी में लगभग ₹{price} प्रति क्विंटल पर भाव तय करें।",
                "net": "ढुलाई घटाने के बाद खेत पर अनुमानित शुद्ध मूल्य ₹{price} प्रति क्विंटल है।",
                "latest": "ताज़ा मंडी भाव ₹{price} प्रति क्विंटल रहा और कुल आवक {arrivals} क्विंटल दर्ज हुई।",
                "forecast": "एआरआईएमए अनुमान अगले महीने ₹{price} प्रति क्विंटल का संकेत देता है।",
                "supply": "आपूर्ति दबाव सूचकांक {value} है, इसलिए भाव सीमा समायोजित रखिए।",
                "transport": "आकलित ढुलाई खर्च ₹{cost} प्रति क्विंटल है (लगभग {distance} किमी की दूरी)।",
            },
            "mr": {
                "negotiate": "{market} बाजारात सुमारे ₹{price} प्रति क्विंटल भावावर चर्चा करा.",
                "net": "वाहतूक वजा केल्यानंतर शेतपातळीवरील शुद्ध दर अंदाजे ₹{price} प्रति क्विंटल राहील.",
                "latest": "अलीकडील बाजारभाव ₹{price} प्रति क्विंटल असून एकूण आवक {arrivals} क्विंटल नोंदली गेली.",
                "forecast": "एआरआयएमए अंदाज पुढील महिन्यासाठी ₹{price} प्रति क्विंटल सूचित करतो.",
                "supply": "पुरवठा दडपण निर्देशांक {value} असल्याने दरपट्टी योग्यरीत्या जपून बोला.",
                "transport": "वाहतूक खर्चाचा अंदाज ₹{cost} प्रति क्विंटल (अंदाजे {distance} किमी अंतर).",
            },
        }
        templates = language_templates.get(language)
        if not templates:
            return ""

        sentence_patterns = [
            (
                re.compile(r"Negotiate around ₹(?P<price>\d+(?:\.\d+)?) per quintal at (?P<market>[^.]+)\.", re.IGNORECASE),
                "negotiate",
            ),
            (
                re.compile(r"After subtracting transport, expected net is ₹(?P<price>\d+(?:\.\d+)?)\.", re.IGNORECASE),
                "net",
            ),
            (
                re.compile(
                    r"Latest mandi modal price is ₹(?P<price>\d+(?:\.\d+)?)\/qtl with arrivals (?P<arrivals>\d+(?:\.\d+)?) qtl\.",
                    re.IGNORECASE,
                ),
                "latest",
            ),
            (
                re.compile(r"ARIMA forecast for next month suggests ₹(?P<price>\d+(?:\.\d+)?)\/qtl\.", re.IGNORECASE),
                "forecast",
            ),
            (
                re.compile(r"Supply pressure indicator at (?P<value>-?\d+(?:\.\d+)?) adjusts negotiation band\.", re.IGNORECASE),
                "supply",
            ),
            (
                re.compile(r"Estimated transport cost is ₹(?P<cost>\d+(?:\.\d+)?)\/qtl over (?P<distance>\d+(?:\.\d+)?) km\.", re.IGNORECASE),
                "transport",
            ),
        ]

        sentences = [s.strip() for s in re.split(r"(?<=\.)\s+", text) if s.strip()]
        translated_sentences = []
        changed = False
        for sentence in sentences:
            matched = False
            for pattern, key in sentence_patterns:
                match = pattern.match(sentence)
                if match:
                    template = templates.get(key)
                    if not template:
                        continue
                    translated = template.format(**match.groupdict())
                    translated_sentences.append(translated)
                    changed = True
                    matched = True
                    break
            if not matched:
                translated_sentences.append(sentence)

        if not changed:
            return ""
        return " ".join(translated_sentences)
