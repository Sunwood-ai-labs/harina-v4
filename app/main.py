from __future__ import annotations

import logging

from app.bot import ReceiptBot
from app.config import load_settings


logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")


def main() -> None:
    settings = load_settings(require_discord=True, require_gemini=True, require_google_workspace=True)
    bot = ReceiptBot(settings=settings)
    bot.run(settings.require_discord_token(), log_handler=None)


if __name__ == "__main__":
    main()
