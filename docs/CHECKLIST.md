# Deliverable Checklist

| Requirement | Implementation Notes | Status |
|-------------|----------------------|--------|
| Conversational AI advises on negotiation | `FarmerAdvisor` blends modal price history, ARIMA forecast, supply arrivals, and transport costs to produce negotiation briefs (`app/services/recommendation.py`). | ✅ |
| ARIMA-based price prediction | `ArimaForecastService` (SARIMAX) with fallbacks; exposed through Flask UI chart and notebook demo. | ✅ |
| Optimal sale timing & locations | `/api/recommendation` returns `best_sale_window` (peak forecast) and `top_markets` (aggregated from live data.gov.in prices). | ✅ |
| Warn against market exploitation | Heuristics flag depressed prices/supply gluts; surfaced in UI warning panel and Telegram responses. | ✅ |
| Educate on schemes/cooperatives/post-harvest | JSON knowledge base rendered in UI and API responses. | ✅ |
| Voice-based interaction for low literacy | Telegram bot + Vosk STT + gTTS cached audio (`app/services/voice.py`, `app/services/telegram_bot.py`). | ✅ |
| Operate in low-connectivity environment | JSON cache, prewarm script, offline translation templates, Vosk models, gTTS cache. | ✅ |
| Use data.gov.in resource IDs (agriculture domain) | Live integration via `app/services/data_gov_client.py`; feeds documented in `docs/DATA_APIS.md`. | ✅ |
| Coverage beyond Maharashtra | Wizard & bot pull commodity/market/state lists and prices from data.gov.in, falling back to local CSV only when live data is unavailable. | ✅ |
| Flask backend with PostgreSQL logging | `webapp` package + `app/db.py` (SQLAlchemy) store query latency and status in Postgres. | ✅ |
| Response < 10 seconds | Cached pandas dataset + ARIMA forecast executes synchronously; latency recorded per request and surfaced in UI pill. | ✅ |
