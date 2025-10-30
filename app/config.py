from pathlib import Path
from functools import lru_cache
from typing import List, Optional

from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "data"
CACHE_DIR = DATA_DIR / "cache"
RAW_DATA_PATH = DATA_DIR / "raw" / "maharashtra_monthly_prices.csv"


class MarketConfig(BaseModel):
    name: str
    state: str
    latitude: float
    longitude: float
    truck_rate_per_km: float = Field(
        6.5, description="Approximate INR cost per km for 10-ton truck"
    )
    last_mile_markup: float = Field(
        0.12, description="Percentage markup added for local handling"
    )


class AppSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    gemini_api_key: Optional[str] = Field(
        default=None, validation_alias="GEMINI_API_KEY"
    )
    gov_api_key: Optional[str] = Field(default=None, validation_alias="GOV_API_KEY")
    telegram_bot_token: Optional[str] = Field(
        default=None, validation_alias="TELEGRAM_BOT_TOKEN"
    )
    telegram_allowed_chat_ids: List[int] = Field(
        default_factory=list, validation_alias="TELEGRAM_ALLOWED_CHAT_IDS"
    )
    default_language: str = Field(default="en", validation_alias="DEFAULT_LANGUAGE")
    fallback_language: str = Field(default="hi", validation_alias="FALLBACK_LANGUAGE")
    cache_ttl_minutes: int = Field(default=180)
    max_forecast_horizon_days: int = Field(default=14)
    libretranslate_url: str = Field(
        default="https://libretranslate.de/translate",
        validation_alias="LIBRETRANSLATE_URL",
    )
    database_url: str = Field(
        default="postgresql+psycopg2://farmer:farmer@localhost:5432/farmer_ai",
        validation_alias="DATABASE_URL",
    )
    database_echo: bool = Field(default=False, validation_alias="DATABASE_ECHO")
    markets_config_path: Path = Field(
        default=DATA_DIR / "reference" / "markets.json"
    )
    schemes_path: Path = Field(default=DATA_DIR / "reference" / "schemes.json")
    cooperatives_path: Path = Field(
        default=DATA_DIR / "reference" / "cooperatives.json"
    )
    post_harvest_path: Path = Field(
        default=DATA_DIR / "reference" / "post_harvest.json"
    )


@lru_cache()
def get_settings() -> AppSettings:
    return AppSettings()


__all__ = [
    "AppSettings",
    "MarketConfig",
    "PROJECT_ROOT",
    "DATA_DIR",
    "CACHE_DIR",
    "RAW_DATA_PATH",
    "get_settings",
]
