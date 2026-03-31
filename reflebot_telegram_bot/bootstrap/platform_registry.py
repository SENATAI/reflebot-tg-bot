from __future__ import annotations

from dataclasses import dataclass

from aiogram import Bot, Router

from reflebot_telegram_bot.backend.compatibility import TelegramBackendIdentityMapper
from reflebot_telegram_bot.core.ports import BackendIdentityMapper, PlatformSender
from reflebot_telegram_bot.platforms.telegram.adapter import TelegramAdapter
from reflebot_telegram_bot.settings import Settings


@dataclass(slots=True)
class PlatformBundle:
    name: str
    sender: PlatformSender
    router: Router


def create_backend_identity_mapper(settings: Settings) -> BackendIdentityMapper:
    if settings.platform_adapter == "telegram":
        return TelegramBackendIdentityMapper()

    raise NotImplementedError(
        f"Platform adapter '{settings.platform_adapter}' is not implemented yet."
    )


def create_platform_bundle(
    *,
    settings: Settings,
    bot: Bot,
    start_use_case,
    button_use_case,
    text_use_case,
    file_use_case,
) -> PlatformBundle:
    if settings.platform_adapter == "telegram":
        adapter = TelegramAdapter(
            bot=bot,
            settings=settings,
            start_use_case=start_use_case,
            button_use_case=button_use_case,
            text_use_case=text_use_case,
            file_use_case=file_use_case,
        )
        return PlatformBundle(
            name="telegram",
            sender=adapter.sender,
            router=adapter.router,
        )

    raise NotImplementedError(
        f"Platform adapter '{settings.platform_adapter}' is not implemented yet."
    )
