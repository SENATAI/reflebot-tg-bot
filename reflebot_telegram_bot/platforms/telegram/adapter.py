from __future__ import annotations

from aiogram import Bot

from reflebot_telegram_bot.core.planner import ResponsePlanner
from reflebot_telegram_bot.core.use_cases.button import ButtonUseCase
from reflebot_telegram_bot.core.use_cases.file import FileUseCase
from reflebot_telegram_bot.core.use_cases.start import StartUseCase
from reflebot_telegram_bot.core.use_cases.text import TextUseCase
from reflebot_telegram_bot.platforms.telegram.router import build_telegram_router
from reflebot_telegram_bot.platforms.telegram.sender import TelegramSender
from reflebot_telegram_bot.platforms.telegram.update_mapper import TelegramUpdateMapper
from reflebot_telegram_bot.settings import Settings


class TelegramAdapter:
    def __init__(
        self,
        *,
        bot: Bot,
        settings: Settings,
        start_use_case: StartUseCase,
        button_use_case: ButtonUseCase,
        text_use_case: TextUseCase,
        file_use_case: FileUseCase,
    ) -> None:
        self.sender = TelegramSender(bot)
        self.update_mapper = TelegramUpdateMapper(bot)
        self.router = build_telegram_router(
            update_mapper=self.update_mapper,
            start_use_case=start_use_case,
            button_use_case=button_use_case,
            text_use_case=text_use_case,
            file_use_case=file_use_case,
            sender=self.sender,
            planner=ResponsePlanner(),
            settings=settings,
        )
