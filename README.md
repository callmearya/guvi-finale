# Farmer Negotiation Assistant

Conversational decision-support tool that helps Indian farmers negotiate fair mandi prices by combining historical price trends, ARIMA-based forecasts, transport cost estimates, market sentiment indicators, and educational nudges about schemes, cooperatives, and post-harvest practices. The assistant is designed to run in low-connectivity settings, supports regional languages, and plugs into a free-to-use Telegram channel for messaging plus cached voice interactions.

## Key Capabilities
- **Price intelligence**: blends recent modal prices, arrivals-based supply pressure, and ARIMA forecasts (statsmodels) to recommend negotiation ranges together with transparent reasoning.
- **Cost aware**: estimates per-quintal logistics cost using reference mandi coordinates and farmer district centroids so farmers understand farm-gate net value.
- **Explainable guidance**: every suggestion lists the facts, numerical drivers, and potential exploitation warnings.
- **Regional language delivery**: responses auto-translate to Hindi/Marathi via Gemini 2.5 Flash Lite when available, with template fallbacks and optional LibreTranslate endpoint for other deployments.
- **Voice readiness**: offline Vosk models + gTTS based caching enable speech-to-text commands and audio summaries for low-literacy farmers via Telegram voice notes.
- **Grassroots knowledge**: curated government scheme briefs, cooperative opportunities, and commodity-specific post-harvest practices shipped locally in JSON.
- **Offline-first caching**: JSON cache for API hits, forecasts, and text-to-speech files so the system keeps working during connectivity dips.

## Data Sources
- **Live**: Agmarknet Daily Market Prices, State Aggregated Arrivals, and e-NAM snapshots pulled via data.gov.in APIs (see [`docs/DATA_APIS.md`](docs/DATA_APIS.md)).
- **Seed**: Maharashtra monthly commodity prices (`data/raw/maharashtra_monthly_prices.csv`) sourced from [`joshi-vipul/maharashtra_mandi`](https://github.com/joshi-vipul/maharashtra_mandi) for offline fallback.
- Static reference files under `data/reference/` cover schemes, cooperatives, and post-harvest advisories; dynamic market/state/district listings now come from the data.gov.in feeds.

## Project Structure
```
app/
  config.py              # Pydantic settings loader (env + defaults)
  main.py                # FastAPI application entrypoint
  models/schemas.py      # Pydantic request/response contracts
  services/
    data_provider.py     # Historical data ingest with API fallback + caching
    forecast.py          # ARIMA/SARIMAX forecaster
    recommendation.py    # Core negotiation reasoning pipeline
    transport.py         # Logistics cost estimator
    education_service.py # Schemes/cooperatives/post-harvest tips
    localization.py      # Translation helpers + Gemini + template fallback
    gemini_client.py     # Thin Gemini wrapper
    telegram_bot.py      # Python Telegram Bot interface with voice support
    voice.py             # gTTS + Vosk utilities (cached)
    utils/cache.py       # JSON cache helper
scripts/
  run_api.sh             # Launch FastAPI via uvicorn
  start_bot.py           # Start Telegram bot after configuring token
  precache.py            # Warm essential caches for offline use
notebooks/
  price_forecasting.ipynb # SARIMAX walkthrough on real mandi data
```

## Getting Started
1. **Python environment**
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ```
2. **Environment variables**: copy `.env.example` to `.env` and set at least:
   - `GEMINI_API_KEY` (optional, enables higher quality reasoning + translations; free tier available via Google AI Studio).
   - `GOV_API_KEY` (data.gov.in key – required for all-India mandi coverage).
   - `TELEGRAM_BOT_TOKEN` (create a free bot via [@BotFather](https://t.me/BotFather)).
   - `LIBRETRANSLATE_URL` (optional self/hosted LibreTranslate endpoint to extend language coverage without Gemini).

3. **Run FastAPI microservice (optional)**
   ```bash
   ./scripts/run_api.sh
   # -> FastAPI available at http://localhost:8000
   # Try: curl -X POST http://localhost:8000/recommendation -H 'content-type: application/json' \
   #       -d '{"commodity":"Onion","market":"Lasalgaon","quantity_qtl":20,"district":"Nashik","state":"Maharashtra","preferred_language":"hi"}'
   ```

4. **Flask web experience (user-facing UI)**
   ```bash
   ./scripts/run_flask.sh
   # -> Flask serves http://localhost:5000 with interactive dashboard
   ```
   The UI now guides farmers through a touch-friendly wizard backed by national data.gov.in APIs:
   - Step 1: pick preferred language (Hindi, Marathi, English) with one tap
   - Step 2–3: choose crop and mandi from large buttons with search-as-you-type
   - Step 4: set quantity via quick picks or slider, plus forecast horizon presets
   - Step 5: optionally choose state/district for transport estimates
   The wizard highlights the response latency (<10 s target) and surfaces the final brief with charts, warnings, schemes, cooperatives, and post-harvest tips.

5. **Telegram bot (free messaging channel)**
   ```bash
   python scripts/start_bot.py
   ```
   - Allowed chat IDs can be whitelisted via `TELEGRAM_ALLOWED_CHAT_IDS`.
   - The conversation mirrors the web wizard: language → crop → mandi → quantity → forecast horizon → state/district, all through inline buttons. Farmers can still type or send voice notes, but the button flow eliminates the need for command syntax.

6. **Voice setup (optional)**
   - Download Vosk lightweight models (e.g. Hindi) into `voice/`: see [`docs/VOICE_SETUP.md`](docs/VOICE_SETUP.md).
   - Ensure `ffmpeg` is installed for Telegram OGG → WAV conversion.

7. **Prewarm caches for offline deployments**
   ```bash
   python scripts/precache.py
   ```
   Populates `data/cache/` with recent recommendations so the assistant can answer even without internet.

8. **ARIMA notebook**

## PostgreSQL Integration
- Configure `DATABASE_URL` in `.env` (e.g. `postgresql+psycopg2://farmer:farmer@localhost:5432/farmer_ai`).
- Tables are auto-created on first request (`query_logs` table stores commodity/market queries, duration, warning flags).
- Enable SQL echo logs with `DATABASE_ECHO=true` for troubleshooting.

The Flask API writes each recommendation call to PostgreSQL alongside latency metrics, helping monitor the <10 second SLA.
   - Open `notebooks/price_forecasting.ipynb` in Jupyter to reproduce the SARIMAX forecast used in production (uses real Lasalgaon onion series).

## Low-Connectivity Operation
- `app/utils/cache.JsonCache` persists JSON payloads (price snapshots, forecast results, TTS audio) inside `data/cache/` with manageable TTLs.
- `scripts/precache.py` can be run on a machine with internet and the cache folder synced to field devices.
- Translation fallback templates ensure essential guidance is still delivered in Hindi/Marathi even when remote AI services are unavailable.

## Free Service Choices
- **Messaging**: Telegram Bot API (free-tier).
- **AI reasoning**: Google Gemini 2.5 Flash Lite (generous free quota). Without a key, code falls back to heuristic reasoning only.
- **Translations**: Optional LibreTranslate endpoint (self-hostable) or built-in template translations.
- **Speech**: Vosk offline models (Apache 2.0) and gTTS for cached audio (free web API).

## Next Steps
- Extend `data/reference/` with more states/commodities.
- Integrate additional supply-demand feeds (Agmarknet live API) once a dedicated key is provisioned.
- Package the FastAPI app into a container for deployment on low-cost edge hardware (Raspberry Pi/Jetson).
