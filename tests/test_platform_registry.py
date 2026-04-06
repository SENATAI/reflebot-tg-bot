from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from reflebot_telegram_bot.bootstrap.platform_registry import (
    create_backend_identity_mapper,
    create_platform_bundle,
)
from reflebot_telegram_bot.settings import Settings


def test_create_backend_identity_mapper_for_telegram(settings) -> None:
    mapper = create_backend_identity_mapper(settings)

    assert mapper.login_username(
        SimpleNamespace(platform="telegram", username="@tester")
    ) == "tester"


def test_create_backend_identity_mapper_raises_for_unsupported_platform(settings) -> None:
    unsupported = Settings(
        TELEGRAM_BOT_TOKEN="token",
        REFLEBOT_BACKEND_BASE_URL="http://127.0.0.1:8080",
        REFLEBOT_API_PREFIX="/api/reflections",
        REFLEBOT_TELEGRAM_SECRET_TOKEN="secret",
        RABBITMQ_URL="amqp://guest:guest@127.0.0.1:5672/",
        RABBITMQ_NOTIFICATIONS_EXCHANGE="reflebot.notifications",
        RABBITMQ_REFLECTION_PROMPT_QUEUE="bot.reflection-prompts",
        RABBITMQ_REFLECTION_PROMPT_ROUTING_KEY="reflection_prompt.send",
        RABBITMQ_NOTIFICATION_RESULTS_EXCHANGE="reflebot.notification-results",
        RABBITMQ_DELIVERY_RESULT_QUEUE="backend.notification-results",
        RABBITMQ_DELIVERY_RESULT_ROUTING_KEY="reflection_prompt.result",
        PLATFORM_ADAPTER="max",
    )

    with pytest.raises(NotImplementedError):
        create_backend_identity_mapper(unsupported)


@pytest.mark.asyncio()
async def test_create_platform_bundle_for_telegram(settings) -> None:
    bot = SimpleNamespace(
        download=AsyncMock(),
        edit_message_text=AsyncMock(),
        send_message=AsyncMock(),
        send_document=AsyncMock(),
        send_video=AsyncMock(),
        send_video_note=AsyncMock(),
        answer_callback_query=AsyncMock(),
        set_my_commands=AsyncMock(),
    )
    bundle = create_platform_bundle(
        settings=settings,
        bot=bot,
        start_use_case=AsyncMock(),
        button_use_case=AsyncMock(),
        text_use_case=AsyncMock(),
        file_use_case=AsyncMock(),
    )

    assert bundle.name == "telegram"
    assert bundle.router is not None
    assert bundle.sender.platform_name == "telegram"
    await bundle.startup()
    bot.set_my_commands.assert_awaited_once()
