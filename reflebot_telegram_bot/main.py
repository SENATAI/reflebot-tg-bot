from __future__ import annotations

import asyncio

from reflebot_telegram_bot.app import Application
from reflebot_telegram_bot.logging import configure_logging
from reflebot_telegram_bot.settings import get_settings


async def run() -> None:
    settings = get_settings()
    configure_logging(settings.log_level)
    application = Application(settings)
    await application.run()


def main() -> None:
    asyncio.run(run())
