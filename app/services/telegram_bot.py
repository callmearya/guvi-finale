from __future__ import annotations

import shlex
import re
from difflib import get_close_matches
from pathlib import Path
from typing import Any, Dict, List, Optional

from pydub import AudioSegment
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from app.config import get_settings
from app.models.schemas import RecommendationRequest
from app.services.localization import LocalizationService
from app.services.recommendation import FarmerAdvisor
from app.services.voice import VoiceService

NUMBER_WORDS = {
    "zero": 0,
    "one": 1,
    "two": 2,
    "three": 3,
    "four": 4,
    "five": 5,
    "six": 6,
    "seven": 7,
    "eight": 8,
    "nine": 9,
    "ten": 10,
    "eleven": 11,
    "twelve": 12,
    "thirteen": 13,
    "fourteen": 14,
    "fifteen": 15,
    "sixteen": 16,
    "seventeen": 17,
    "eighteen": 18,
    "nineteen": 19,
    "twenty": 20,
    "thirty": 30,
    "forty": 40,
    "fifty": 50,
    "sixty": 60,
    "seventy": 70,
    "eighty": 80,
    "ninety": 90,
    "hundred": 100,
}

FIELD_BREAK_PATTERN = re.compile(r"\b(?:and then|and|then|please|with|after|next|so|now|thanks)\b")


class TelegramFarmerBot:
    """Guided Telegram assistant with button-first flow for farmers."""

    def __init__(self, advisor: FarmerAdvisor, token: str) -> None:
        self.settings = get_settings()
        self.advisor = advisor
        self.token = token
        self.voice_service = VoiceService()
        self.user_preferences: Dict[int, Dict[str, Optional[str]]] = {}
        self.sessions: Dict[int, Dict[str, Any]] = {}
        self.localizer = LocalizationService()
        self.language_aliases = {
            "english": "en",
            "inglish": "en",
            "en": "en",
            "hindi": "hi",
            "hi": "hi",
            "hind": "hi",
            "hinglish": "hi",
            "marathi": "mr",
            "mr": "mr",
            "mar": "mr",
        }

        provider = self.advisor.provider
        self.commodity_options = provider.list_commodities()[:80]
        self.state_options = provider.list_states()
        self.state_district_map = {state: provider.list_districts(state) for state in self.state_options}
        self.market_cache: Dict[tuple[str, Optional[str]], List[str]] = {}
        all_districts: List[str] = []
        for values in self.state_district_map.values():
            all_districts.extend(values)
        self.all_districts = sorted({district for district in all_districts})

        self.language_options = [
            {"code": "hi", "label": "हिन्दी"},
            {"code": "mr", "label": "मराठी"},
            {"code": "en", "label": "English"},
        ]

        self.prompts = {
            "en": {
                "welcome": "Namaste! Let's plan your sale step by step.",
                "pick_language": "Choose your language:",
                "pick_commodity": "Which crop are you selling?",
                "send_commodity_text": "Please type the crop name.",
                "pick_market": "Select the mandi you plan to visit.",
                "send_market_text": "Please type the mandi name.",
                "pick_quantity": "How many quintals will you carry?",
                "pick_horizon": "How many days ahead should we forecast?",
                "pick_state": "Select your state (or type it).",
                "pick_district": "Now choose your district (or type it).",
                "custom_quantity": "Type the quantity in quintals (number).",
                "processing": "Working out your negotiation brief…",
                "unknown": "I didn't understand that. Please use the buttons or type the requested info.",
                "other_button": "Other",
                "custom_button": "Custom",
                "skip_button": "Skip",
                "quantity_unit": "qtl",
                "horizon_unit": "days",
            },
            "hi": {
                "welcome": "नमस्ते! चलिए कदम-दर-कदम बिक्री योजना बनाते हैं।",
                "pick_language": "अपनी भाषा चुनें:",
                "pick_commodity": "आप कौन सा फसल बेचेंगे?",
                "send_commodity_text": "कृपया फसल का नाम लिखें।",
                "pick_market": "किस मंडी में जाना चाहते हैं?",
                "send_market_text": "कृपया मंडी का नाम लिखें।",
                "pick_quantity": "कितने क्विंटल ले जा रहे हैं?",
                "pick_horizon": "कितने दिनों का पूर्वानुमान चाहिए?",
                "pick_state": "अपने राज्य का चयन करें (या नाम लिखें)।",
                "pick_district": "अब अपना ज़िला चुनें (या नाम लिखें)।",
                "custom_quantity": "क्विंटल में मात्रा लिखें (केवल संख्या)।",
                "processing": "आपकी सलाह तैयार की जा रही है…",
                "unknown": "समझ नहीं पाया। कृपया बटन का उपयोग करें या मांगी गई जानकारी लिखें।",
                "other_button": "अन्य",
                "custom_button": "अपना लिखें",
                "skip_button": "छोड़ें",
                "quantity_unit": "क्विंटल",
                "horizon_unit": "दिन",
            },
            "mr": {
                "welcome": "नमस्कार! चला पायरी-पायरीने विक्रीची योजना करूया.",
                "pick_language": "आपली भाषा निवडा:",
                "pick_commodity": "कोणते पीक विकणार आहात?",
                "send_commodity_text": "कृपया पीकाचे नाव लिहा.",
                "pick_market": "कोणत्या बाजारात जाणार आहात?",
                "send_market_text": "कृपया बाजाराचे नाव लिहा.",
                "pick_quantity": "किती क्विंटल नेणार आहात?",
                "pick_horizon": "किती दिवसांचा अंदाज हवा आहे?",
                "pick_state": "आपले राज्य निवडा (किंवा नाव लिहा).",
                "pick_district": "आता आपला जिल्हा निवडा (किंवा नाव लिहा).",
                "custom_quantity": "क्विंटलची संख्या लिहा (फक्त संख्या).",
                "processing": "तुमची माहिती तयार केली जात आहे…",
                "unknown": "समजले नाही. कृपया बटणे वापरा किंवा माहिती लिहा.",
                "other_button": "इतर",
                "custom_button": "स्वतः लिहा",
                "skip_button": "वगळा",
                "quantity_unit": "क्विंटल",
                "horizon_unit": "दिवस",
            },
        }

    def _get_user_pref(self, chat_id: int) -> Dict[str, Optional[str]]:
        if chat_id not in self.user_preferences:
            self.user_preferences[chat_id] = {
                "language": self.settings.fallback_language,
                "district": None,
                "state": None,
            }
        return self.user_preferences[chat_id]

    @staticmethod
    def _parse_number_phrase(phrase: Optional[str]) -> Optional[int]:
        if not phrase:
            return None
        digits = re.search(r"\d+", phrase)
        if digits:
            try:
                return int(digits.group())
            except ValueError:
                pass
        words = re.findall(r"[a-z]+", phrase.lower())
        if not words:
            return None
        total = 0
        current = 0
        for word in words:
            if word not in NUMBER_WORDS:
                continue
            value = NUMBER_WORDS[word]
            if value == 100:
                if current == 0:
                    current = 1
                current *= value
            else:
                current += value
        total += current
        return total or None

    @staticmethod
    def _clean_fragment(fragment: str, remove_units: Optional[List[str]] = None) -> str:
        value = FIELD_BREAK_PATTERN.split(fragment)[0]
        if remove_units:
            for unit in remove_units:
                value = value.replace(unit, " ")
        value = re.sub(r"[^a-z0-9\s-]", " ", value.lower())
        value = re.sub(r"\s+", " ", value).strip()
        return value

    def _capture_phrase(
        self,
        text: str,
        keywords: List[str],
        remove_units: Optional[List[str]] = None,
    ) -> Optional[str]:
        pattern = (
            r"(?:"
            + "|".join(re.escape(key) for key in keywords)
            + r")\b(?:\s+(?:is|=|at|for|will be|should be|to|in|around|about|of))?\s+(?P<value>[a-z0-9\s\-]+)"
        )
        match = re.search(pattern, text)
        if not match:
            return None
        fragment = match.group("value")
        cleaned = self._clean_fragment(fragment, remove_units)
        return cleaned or None

    def _match_language(self, phrase: str) -> Optional[str]:
        words = phrase.split()
        for word in words:
            if word in self.language_aliases:
                return self.language_aliases[word]
        return None

    @staticmethod
    def _fuzzy_choice(value: Optional[str], options: List[str], cutoff: float = 0.55) -> Optional[str]:
        if not value:
            return None
        normalized = value.strip().lower()
        if not normalized:
            return None
        mapping = {option.lower(): option for option in options}
        matches = get_close_matches(normalized, list(mapping.keys()), n=1, cutoff=cutoff)
        if matches:
            return mapping[matches[0]]
        return None

    def _extract_voice_fields(self, message: str) -> Dict[str, Any]:
        text = message.lower()
        fields: Dict[str, Any] = {}

        language_phrase = self._capture_phrase(text, ["language", "bhasha"])
        if language_phrase:
            language_code = self._match_language(language_phrase)
            if language_code:
                fields["language"] = language_code

        commodity_phrase = self._capture_phrase(text, ["crop", "commodity", "fasal", "produce"])
        if commodity_phrase:
            fields["commodity"] = commodity_phrase

        market_phrase = self._capture_phrase(text, ["market", "mandi", "bazaar", "bazar"])
        if market_phrase:
            fields["market"] = market_phrase

        quantity_phrase = self._capture_phrase(
            text,
            ["quantity", "qty", "quintal", "quintals", "load", "amount"],
            remove_units=["quintals", "quintal", "qtls", "qtl"],
        )
        quantity_value = self._parse_number_phrase(quantity_phrase)
        if quantity_value:
            fields["quantity"] = quantity_value

        horizon_phrase = self._capture_phrase(
            text,
            ["forecast", "horizon", "days", "prediction"],
            remove_units=["days", "day"],
        )
        horizon_value = self._parse_number_phrase(horizon_phrase)
        if horizon_value:
            fields["horizon"] = horizon_value

        state_phrase = self._capture_phrase(text, ["state", "rajya", "province"])
        if state_phrase:
            fields["state"] = state_phrase

        district_phrase = self._capture_phrase(text, ["district", "zilla", "zila", "taluka", "taluk"])
        if district_phrase:
            fields["district"] = district_phrase

        return fields

    def _session(self, chat_id: int) -> Dict[str, Any]:
        if chat_id not in self.sessions:
            self.sessions[chat_id] = {"step": "language", "data": {}, "awaiting": None}
        return self.sessions[chat_id]

    def _reset_session(self, chat_id: int) -> None:
        self.sessions[chat_id] = {"step": "language", "data": {}, "awaiting": None}

    def _t(self, chat_id: int, key: str) -> str:
        lang = self._get_user_pref(chat_id).get("language", "hi")
        return self.prompts.get(lang, self.prompts["en"]).get(key, key)

    def _is_allowed(self, chat_id: int) -> bool:
        allowed = self.settings.telegram_allowed_chat_ids
        if not allowed:
            return True
        return chat_id in allowed

    def _language_keyboard(self) -> InlineKeyboardMarkup:
        rows = [
            [InlineKeyboardButton(option["label"], callback_data=f"lang:{option['code']}")]
            for option in self.language_options
        ]
        return InlineKeyboardMarkup(rows)

    def _build_keyboard(self, chat_id: int, values: List[str], prefix: str, per_row: int = 2) -> InlineKeyboardMarkup:
        rows: List[List[InlineKeyboardButton]] = []
        for i in range(0, len(values), per_row):
            chunk = values[i : i + per_row]
            rows.append([
                InlineKeyboardButton(text=value, callback_data=f"{prefix}:{value}")
                for value in chunk
            ])
        rows.append([InlineKeyboardButton(self._t(chat_id, "other_button"), callback_data=f"{prefix}:other")])
        return InlineKeyboardMarkup(rows)

    def _format_quantity_label(self, chat_id: int, quantity: float) -> str:
        suffix = self._t(chat_id, "quantity_unit")
        return f"{quantity} {suffix}"

    def _format_horizon_label(self, chat_id: int, days: int) -> str:
        suffix = self._t(chat_id, "horizon_unit")
        return f"{days} {suffix}"

    async def _send_language_prompt(self, chat_id: int, update: Update) -> None:
        self._reset_session(chat_id)
        target = update.message or update.callback_query
        if target:
            await target.reply_text(self._t(chat_id, "welcome"))
            await target.reply_text(self._t(chat_id, "pick_language"), reply_markup=self._language_keyboard())

    def _resolve_markets(self, commodity: Optional[str], state: Optional[str] = None) -> List[str]:
        if not commodity:
            return []
        key = (commodity.strip().lower(), (state or "").strip().lower())
        if key in self.market_cache:
            return self.market_cache[key]

        markets: List[str] = []
        provider = self.advisor.provider

        if provider.gov_client.enabled:
            markets = provider.gov_client.list_markets(commodity=commodity, state=state)
            if not markets and state:
                markets = provider.gov_client.list_markets(commodity=commodity)

        if not markets:
            dataset = provider._load_local_dataset()
            subset = dataset[dataset["Commodity"].str.lower() == commodity.lower()]
            if state:
                subset = subset[subset["state_name"].str.lower() == state.lower()]
            markets = sorted(subset["APMC"].dropna().unique().tolist())

        self.market_cache[key] = markets
        return markets

    def _top_markets(self, commodity: Optional[str], state: Optional[str] = None) -> List[str]:
        return self._resolve_markets(commodity, state)[:10]

    def _top_districts(self, state: str) -> List[str]:
        return (self.state_district_map.get(state) or [])[:10]

    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        chat_id = update.effective_chat.id
        if not self._is_allowed(chat_id):
            return
        await self._send_language_prompt(chat_id, update)

    async def set_language(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        chat_id = update.effective_chat.id
        if not self._is_allowed(chat_id):
            return
        prefs = self._get_user_pref(chat_id)
        if not context.args:
            await update.message.reply_text("Usage: /language en|hi|mr")
            return
        prefs["language"] = context.args[0]
        await update.message.reply_text(f"Language updated to {context.args[0]}")

    async def _send_commodity_prompt(self, chat_id: int, context: ContextTypes.DEFAULT_TYPE) -> None:
        session = self._session(chat_id)
        session["step"] = "commodity"
        options = self.commodity_options[:12]
        await context.bot.send_message(
            chat_id=chat_id,
            text=self._t(chat_id, "pick_commodity"),
            reply_markup=self._build_keyboard(chat_id, options, "commodity"),
        )

    async def _send_market_prompt(self, chat_id: int, context: ContextTypes.DEFAULT_TYPE) -> None:
        session = self._session(chat_id)
        session["step"] = "market"
        commodity = session["data"].get("commodity")
        state_choice = session["data"].get("state")
        markets = self._top_markets(commodity, state_choice)
        if not markets and state_choice:
            markets = self._top_markets(commodity, None)
        await context.bot.send_message(
            chat_id=chat_id,
            text=self._t(chat_id, "pick_market"),
            reply_markup=self._build_keyboard(chat_id, markets or [], "market"),
        )

    async def _send_quantity_prompt(self, chat_id: int, context: ContextTypes.DEFAULT_TYPE) -> None:
        session = self._session(chat_id)
        session["step"] = "quantity"
        qty_rows = [
            [InlineKeyboardButton(self._format_quantity_label(chat_id, value), callback_data=f"quantity:{value}")]
            for value in [5, 10, 15, 20, 25, 30]
        ] + [[InlineKeyboardButton(self._t(chat_id, "custom_button"), callback_data="quantity:other")]]
        await context.bot.send_message(
            chat_id=chat_id,
            text=self._t(chat_id, "pick_quantity"),
            reply_markup=InlineKeyboardMarkup(qty_rows),
        )
        horizon_rows = [
            [InlineKeyboardButton(self._format_horizon_label(chat_id, days), callback_data=f"horizon:{days}")]
            for days in [7, 14, 21, 30]
        ]
        await context.bot.send_message(
            chat_id=chat_id,
            text=self._t(chat_id, "pick_horizon"),
            reply_markup=InlineKeyboardMarkup(horizon_rows),
        )

    async def _send_state_prompt(self, chat_id: int, context: ContextTypes.DEFAULT_TYPE) -> None:
        session = self._session(chat_id)
        session["step"] = "state"
        options = self.state_options[:10]
        await context.bot.send_message(
            chat_id=chat_id,
            text=self._t(chat_id, "pick_state"),
            reply_markup=self._build_keyboard(chat_id, options, "state"),
        )

    async def _send_district_prompt(self, chat_id: int, context: ContextTypes.DEFAULT_TYPE, state_name: str) -> None:
        session = self._session(chat_id)
        session["step"] = "district"
        districts = self._top_districts(state_name)
        keyboard = InlineKeyboardMarkup(
            [[InlineKeyboardButton(name, callback_data=f"district:{name}")] for name in districts]
            + [[InlineKeyboardButton(self._t(chat_id, "skip_button"), callback_data="district:skip")]]
        )
        await context.bot.send_message(
            chat_id=chat_id,
            text=self._t(chat_id, "pick_district"),
            reply_markup=keyboard,
        )

    def _build_request(self, chat_id: int) -> RecommendationRequest:
        session = self._session(chat_id)
        data = session.get("data", {})
        prefs = self._get_user_pref(chat_id)
        return RecommendationRequest(
            commodity=data.get("commodity", "Onion"),
            market=data.get("market", "Lasalgaon"),
            quantity_qtl=float(data.get("quantity", 10)),
            district=data.get("district"),
            state=data.get("state"),
            preferred_language=prefs.get("language", "hi"),
            horizon_days=int(data.get("horizon", 14)),
        )

    async def _send_recommendation(self, chat_id: int, context: ContextTypes.DEFAULT_TYPE) -> None:
        await context.bot.send_message(chat_id=chat_id, text=self._t(chat_id, "processing"))
        try:
            recommendation = self.advisor.recommend(self._build_request(chat_id))
        except Exception as exc:  # noqa: BLE001
            await context.bot.send_message(chat_id=chat_id, text=f"Error: {exc}")
            return

        summary = recommendation.translated_summary or (
            f"Negotiate around ₹{recommendation.recommended_modal_price:.0f}/qtl at {recommendation.mandi}.\n"
            f"After transport, expect ₹{recommendation.recommended_net_price:.0f}/qtl at farm-gate."
        )
        lines = [summary, ""]
        lines.extend(f"• {point.label}: {point.value}" for point in recommendation.snapshot)
        if recommendation.warnings:
            lines.append("\n⚠️ " + " ".join(recommendation.warnings))

        transport = recommendation.transport or {}
        supply = recommendation.supply_demand or {}
        context_lines: List[str] = []
        if transport.get("per_quintal_cost"):
            unit = self._t(chat_id, "quantity_unit")
            context_lines.append(
                f"Transport: ₹{transport['per_quintal_cost']:.0f} / {unit} over {transport.get('distance_km', '')} km"
            )
        if supply.get("supply_pressure") is not None:
            context_lines.append(
                f"Supply pressure indicator: {supply['supply_pressure'] * 100:.1f}%"
            )
        if supply.get("latest_arrivals") is not None:
            unit = self._t(chat_id, "quantity_unit")
            context_lines.append(
                f"Latest arrivals reported: {supply['latest_arrivals']:.0f} {unit}"
            )
        if context_lines:
            lines.extend(["", *context_lines])

        prefs = self._get_user_pref(chat_id)
        language = prefs.get("language", "hi")
        if language != "en":
            lines = self.localizer.translate_many(lines, language)

        await context.bot.send_message(chat_id=chat_id, text="\n".join(lines))
        self._reset_session(chat_id)

    async def on_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        query = update.callback_query
        if not query:
            return
        await query.answer()
        chat_id = query.message.chat.id
        if not self._is_allowed(chat_id):
            return

        session = self._session(chat_id)
        data = session.setdefault("data", {})

        if query.data.startswith("lang:"):
            lang_code = query.data.split(":", 1)[1]
            self._get_user_pref(chat_id)["language"] = lang_code
            await self._send_commodity_prompt(chat_id, context)
            return

        if query.data.startswith("commodity:" ):
            value = query.data.split(":", 1)[1]
            if value == "other":
                session["awaiting"] = "commodity"
                await context.bot.send_message(chat_id=chat_id, text=self._t(chat_id, "send_commodity_text"))
                return
            data["commodity"] = value
            session["awaiting"] = None
            await self._send_market_prompt(chat_id, context)
            return

        if query.data.startswith("market:"):
            value = query.data.split(":", 1)[1]
            if value == "other":
                session["awaiting"] = "market"
                await context.bot.send_message(chat_id=chat_id, text=self._t(chat_id, "send_market_text"))
                return
            data["market"] = value
            session["awaiting"] = None
            await self._send_quantity_prompt(chat_id, context)
            return

        if query.data.startswith("quantity:"):
            value = query.data.split(":", 1)[1]
            if value == "other":
                session["awaiting"] = "quantity"
                await context.bot.send_message(chat_id=chat_id, text=self._t(chat_id, "custom_quantity"))
                return
            data["quantity"] = float(value)
            session["awaiting"] = None
            return

        if query.data.startswith("horizon:"):
            value = int(query.data.split(":", 1)[1])
            if "quantity" not in data:
                data["quantity"] = 10
            data["horizon"] = value
            await self._send_state_prompt(chat_id, context)
            return

        if query.data.startswith("state:"):
            value = query.data.split(":", 1)[1]
            if value == "other":
                session["awaiting"] = "state"
                await context.bot.send_message(chat_id=chat_id, text=self._t(chat_id, "pick_state"))
                return
            data["state"] = value
            session["awaiting"] = None
            await self._send_district_prompt(chat_id, context, value)
            return

        if query.data.startswith("district:"):
            value = query.data.split(":", 1)[1]
            if value == "skip":
                data.pop("district", None)
                await self._send_recommendation(chat_id, context)
                return
            data["district"] = value
            await self._send_recommendation(chat_id, context)
            return

    def _parse_request(self, message: str, chat_id: int) -> RecommendationRequest:
        prefs = self._get_user_pref(chat_id)
        structured = self._extract_voice_fields(message)

        tokens = shlex.split(message)
        payload: Dict[str, str] = {}
        for token in tokens:
            if "=" in token:
                key, value = token.split("=", 1)
                payload[key.strip().lower()] = value.strip()

        commodity_raw = payload.get("commodity") or payload.get("crop") or structured.get("commodity")
        if not commodity_raw and tokens:
            commodity_raw = tokens[0]
        commodity = self._fuzzy_choice(commodity_raw, self.commodity_options, cutoff=0.45)
        if not commodity:
            commodity = commodity_raw.title() if commodity_raw else "Onion"

        state_raw = payload.get("state") or structured.get("state") or prefs.get("state")
        state_choice = self._fuzzy_choice(state_raw, self.state_options, cutoff=0.45)

        market_raw = payload.get("market") or payload.get("mandi") or structured.get("market")
        market_candidates: List[str] = []
        if commodity:
            market_candidates.extend(self._resolve_markets(commodity, state_choice))
            if not market_candidates:
                market_candidates.extend(self._resolve_markets(commodity, None))
        market = self._fuzzy_choice(market_raw, market_candidates, cutoff=0.5) or (market_raw.title() if market_raw else None)
        if not market:
            market = "Lasalgaon"

        quantity_raw = payload.get("qty", payload.get("quantity"))
        quantity_value = None
        if quantity_raw:
            quantity_value = self._parse_number_phrase(quantity_raw)
        if quantity_value is None:
            quantity_value = structured.get("quantity")
        quantity = float(quantity_value or 10)

        horizon_raw = payload.get("horizon") or payload.get("days")
        horizon_value = None
        if horizon_raw:
            horizon_value = self._parse_number_phrase(horizon_raw)
        if horizon_value is None:
            horizon_value = structured.get("horizon")
        horizon = int(horizon_value or 14)

        district_raw = payload.get("district") or structured.get("district") or prefs.get("district")
        district = None
        if district_raw:
            if state_choice and state_choice in self.state_district_map:
                district_options = self.state_district_map[state_choice]
            else:
                district_options = self.all_districts
            district = self._fuzzy_choice(district_raw, district_options, cutoff=0.5)

        language_raw = payload.get("language") or structured.get("language")
        language = None
        if isinstance(language_raw, str):
            language = self._match_language(language_raw)
        elif language_raw:
            language = language_raw
        if not language:
            language = prefs.get("language", "hi")

        prefs["district"] = district
        prefs["state"] = state_choice
        prefs["language"] = language

        return RecommendationRequest(
            commodity=commodity,
            market=market,
            quantity_qtl=quantity,
            district=district,
            state=state_choice,
            preferred_language=language,
            horizon_days=horizon,
        )

    async def _handle_recommendation(self, update: Update, message_text: str) -> None:
        chat_id = update.effective_chat.id
        try:
            request = self._parse_request(message_text, chat_id)
            recommendation = self.advisor.recommend(request)
        except Exception as exc:
            await update.message.reply_text(f"Sorry, could not compute advice: {exc}")
            return

        summary = recommendation.translated_summary or (
            f"Negotiate around ₹{recommendation.recommended_modal_price:.0f}/qtl at {recommendation.mandi}.\n"
            f"After transport, expect ₹{recommendation.recommended_net_price:.0f}/qtl at farm-gate."
        )
        lines = [summary, ""]
        lines.extend(f"- {point.label}: {point.value}" for point in recommendation.snapshot)
        if recommendation.warnings:
            lines.append("")
            lines.append("⚠️ " + " ".join(recommendation.warnings))
        await update.message.reply_text("\n".join(lines))

    async def on_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not update.message or not update.message.text:
            return
        if not self._is_allowed(update.effective_chat.id):
            return
        chat_id = update.effective_chat.id
        session = self._session(chat_id)
        awaiting = session.get("awaiting")
        text = update.message.text.strip()

        if awaiting == "commodity":
            session["data"]["commodity"] = text.title()
            session["awaiting"] = None
            await self._send_market_prompt(chat_id, context)
            return

        if awaiting == "market":
            session["data"]["market"] = text.title()
            session["awaiting"] = None
            await self._send_quantity_prompt(chat_id, context)
            return

        if awaiting == "quantity":
            try:
                session["data"]["quantity"] = float(text)
                session["awaiting"] = None
                await self._send_state_prompt(chat_id, context)
            except ValueError:
                await update.message.reply_text(self._t(chat_id, "custom_quantity"))
            return

        if awaiting == "state":
            session["data"]["state"] = text.title()
            session["awaiting"] = None
            await self._send_district_prompt(chat_id, context, text.title())
            return

        if session.get("step") == "district":
            session["data"]["district"] = text.title()
            session["awaiting"] = None
            await self._send_recommendation(chat_id, context)
            return

        if "=" in text:
            await self._handle_recommendation(update, text)
            return

        await update.message.reply_text(self._t(chat_id, "unknown"))

    async def on_voice(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not update.message or not update.message.voice:
            return
        if not self._is_allowed(update.effective_chat.id):
            return
        voice = update.message.voice
        file = await context.bot.get_file(voice.file_id)
        ogg_path = Path("voice") / f"{voice.file_unique_id}.oga"
        wav_path = ogg_path.with_suffix(".wav")
        await file.download_to_drive(str(ogg_path))
        try:
            audio = AudioSegment.from_file(ogg_path)
            audio = audio.set_channels(1).set_frame_rate(16000).set_sample_width(2)
            audio.export(wav_path, format="wav")
        except Exception:
            await update.message.reply_text(
                "Unable to decode voice note. Ensure ffmpeg is installed for audio conversion."
            )
            return

        prefs = self._get_user_pref(update.effective_chat.id)
        text = self.voice_service.speech_to_text(wav_path, prefs.get("language", "hi"))
        if not text:
            await update.message.reply_text(
                "Could not understand the voice note. Please repeat slowly or send text."
            )
            return

        await self._handle_recommendation(update, text)

    def run(self) -> None:
        application = Application.builder().token(self.token).build()
        application.add_handler(CommandHandler("start", self.start))
        application.add_handler(CommandHandler("language", self.set_language))
        application.add_handler(CallbackQueryHandler(self.on_callback))
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.on_message))
        application.add_handler(MessageHandler(filters.VOICE, self.on_voice))
        print("✅ Telegram bot polling… Press Ctrl+C to stop.")
        application.run_polling(drop_pending_updates=True)
