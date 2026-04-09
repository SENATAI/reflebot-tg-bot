from __future__ import annotations

from aiogram import Bot

from reflebot_telegram_bot.core.planner import ResponsePlanner
from reflebot_telegram_bot.core.ports import BackendWorkflowPort
from reflebot_telegram_bot.core.use_cases.button import ButtonUseCase
from reflebot_telegram_bot.core.use_cases.file import FileUseCase
from reflebot_telegram_bot.core.use_cases.start import StartUseCase
from reflebot_telegram_bot.core.use_cases.text import TextUseCase
from reflebot_telegram_bot.platforms.telegram.commands import register_menu_commands
from reflebot_telegram_bot.platforms.telegram.rate_limiter import SlidingWindowRateLimiter
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
        backend_workflow: BackendWorkflowPort,
        start_use_case: StartUseCase,
        button_use_case: ButtonUseCase,
        text_use_case: TextUseCase,
        file_use_case: FileUseCase,
    ) -> None:
        self.sender = TelegramSender(
            bot,
            rate_limiter=SlidingWindowRateLimiter(
                settings.telegram_global_rate_limit_per_second,
            ),
        )
        self.update_mapper = TelegramUpdateMapper(bot)
        self.router = build_telegram_router(
            update_mapper=self.update_mapper,
            backend_workflow=backend_workflow,
            start_use_case=start_use_case,
            button_use_case=button_use_case,
            text_use_case=text_use_case,
            file_use_case=file_use_case,
            sender=self.sender,
            planner=ResponsePlanner(),
            settings=settings,
        )

        self._bot = bot

    async def startup(self) -> None:
        await register_menu_commands(self._bot)
