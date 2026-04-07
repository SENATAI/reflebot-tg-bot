from __future__ import annotations

import logging

import httpx
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties

from reflebot_telegram_bot.backend.client import BackendApiClient
from reflebot_telegram_bot.backend.gateway import BackendGateway
from reflebot_telegram_bot.broker.consumer import ReflectionPromptConsumer
from reflebot_telegram_bot.bootstrap.platform_registry import (
    create_backend_identity_mapper,
    create_platform_bundle,
)
from reflebot_telegram_bot.core.planner import ResponsePlanner
from reflebot_telegram_bot.core.use_cases.broker_prompt import BrokerPromptUseCase
from reflebot_telegram_bot.core.use_cases.button import ButtonUseCase
from reflebot_telegram_bot.core.use_cases.file import FileUseCase
from reflebot_telegram_bot.core.use_cases.start import StartUseCase
from reflebot_telegram_bot.core.use_cases.text import TextUseCase
from reflebot_telegram_bot.settings import Settings

logger = logging.getLogger(__name__)


class Application:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.bot = Bot(
            token=settings.telegram_token,
            default=DefaultBotProperties(parse_mode="HTML"),
        )
        self.dispatcher = Dispatcher()
        self.http_client = httpx.AsyncClient(
            base_url=settings.backend_api_url,
            timeout=settings.http_timeout_seconds,
        )
        self.api_client = BackendApiClient(self.http_client, settings)
        self.identity_mapper = create_backend_identity_mapper(settings)
        self.planner = ResponsePlanner()
        self.backend_gateway = BackendGateway(self.api_client, self.identity_mapper)
        self.start_use_case = StartUseCase(self.backend_gateway, self.planner)
        self.button_use_case = ButtonUseCase(self.backend_gateway, self.planner)
        self.text_use_case = TextUseCase(self.backend_gateway, self.planner)
        self.file_use_case = FileUseCase(self.backend_gateway, self.planner)
        self.platform_bundle = None
        self.broker_prompt_use_case = None
        self.consumer = ReflectionPromptConsumer(
            settings=settings,
            broker_prompt_use_case=self._build_broker_prompt_use_case(),
            platform_sender=self._build_platform_bundle().sender,
        )
        self._wire_dispatcher()

    def _build_platform_bundle(self):
        if self.platform_bundle is None:
            self.platform_bundle = create_platform_bundle(
                settings=self.settings,
                bot=self.bot,
                backend_workflow=self.backend_gateway,
                start_use_case=self.start_use_case,
                button_use_case=self.button_use_case,
                text_use_case=self.text_use_case,
                file_use_case=self.file_use_case,
            )
        return self.platform_bundle

    def _build_broker_prompt_use_case(self) -> BrokerPromptUseCase:
        if self.broker_prompt_use_case is None:
            self.broker_prompt_use_case = BrokerPromptUseCase(
                self.planner,
                platform_name=self.settings.platform_adapter,
            )
        return self.broker_prompt_use_case

    def _wire_dispatcher(self) -> None:
        self.dispatcher.include_router(self._build_platform_bundle().router)

    async def run(self) -> None:
        logger.info("Starting application")
        await self._build_platform_bundle().startup()
        await self.consumer.start()
        try:
            await self.dispatcher.start_polling(
                self.bot,
                allowed_updates=self.dispatcher.resolve_used_update_types(),
            )
        finally:
            await self.shutdown()

    async def shutdown(self) -> None:
        logger.info("Shutting down application")
        await self.consumer.close()
        await self.http_client.aclose()
        await self.bot.session.close()
