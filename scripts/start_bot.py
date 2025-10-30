from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.config import get_settings
from app.services.recommendation import FarmerAdvisor
from app.services.telegram_bot import TelegramFarmerBot


def main() -> None:
    settings = get_settings()
    if not settings.telegram_bot_token:
        raise SystemExit("TELEGRAM_BOT_TOKEN not configured. Add it to .env")
    advisor = FarmerAdvisor()
    bot = TelegramFarmerBot(advisor, settings.telegram_bot_token)
    bot.run()


if __name__ == "__main__":
    main()
