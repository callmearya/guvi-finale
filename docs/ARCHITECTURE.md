# System Architecture

```
Farmer → Telegram/Text/Voice                        Admin → CLI/API
          |                                                |
          v                                                v
  TelegramFarmerBot (python-telegram-bot)        FastAPI (app/main.py)
          |                                                |
          +--> LocalizationService (translation) <---------+
          |                                                |
          +--> VoiceService (Vosk + gTTS cache)            |
          |                                                |
          v                                                v
                  FarmerAdvisor (app/services/recommendation.py)
                            |
                            +--> MandiDataProvider (historical CSV + data.gov.in fallback + cache)
                            |
                            +--> ArimaForecastService (statsmodels SARIMAX + cache)
                            |
                            +--> TransportCostEstimator (haversine, reference rates)
                            |
                            +--> KnowledgeBaseService (schemes, cooperatives, post-harvest)
                            |
                            +--> GeminiClient (optional reasoning polish)

Storage Layout:
- data/raw/                     Raw datasets (downloaded upfront)
- data/reference/               Static JSON knowledge base
- data/cache/                   JSON + TTS caches for low connectivity
- voice/                        Vosk acoustic models
```

## Request Flow
1. **Input** (text message, voice note, API call) → sanitized and mapped to `RecommendationRequest`.
2. **Data gathering**
   - CSV history filtered to commodity/market combination.
   - Optional live API fetch cached through `JsonCache` if GOV API key is present.
   - Supply trend derived from arrivals vs historical mean.
3. **Forecasting**: `ArimaForecastService` trains SARIMAX (order=(1,1,1), seasonal (0,1,1,12)) with monthly aggregation, falling back to rolling mean if insufficient data.
4. **Transport**: `TransportCostEstimator` computes approximate road distance between farmer district centroid and reference mandi coordinate, applying rate/markup to estimate per-quintal logistics cost.
5. **Recommendation synthesis**: Weighted blend of latest modal price, short-term trend, supply penalty, forecast, and transport adjustments yields suggested mandi and farm-gate prices. Transparent reasoning bullets list each numerical driver.
6. **Enrichment**: `KnowledgeBaseService` adds scheme/cooperative/post-harvest guidance filtered by state/commodity.
7. **Localization**: Output summarised in farmer’s language via Gemini (if configured), LibreTranslate (if available), or deterministic template translations for Hindi/Marathi.
8. **Delivery**: Response returned as FastAPI JSON, Telegram message, and optional audio summary.

## Low-Connectivity Considerations
- JSON cache keys (mandi data, forecasts, TTS) are persisted with TTL so recently computed advice remains available offline.
- `scripts/precache.py` seeds cache for priority commodity-market pairs before devices go on-field.
- Translation template fallback does not rely on external APIs.
- Voice recognition runs fully offline once Vosk models are downloaded.

## Extensibility Hooks
- Add new mandi references via `data/reference/markets.json` and `district_centroids.json`.
- Plug additional datasets in `MandiDataProvider` by overriding `_load_local_dataset` or providing new CSVs.
- Extend template translations in `LocalizationService` for other Indic languages.
- Schedule `scripts/precache.py` as a cron job to keep cached forecasts fresh.
