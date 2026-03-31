from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from reflebot_telegram_bot.settings import Settings


@pytest.fixture()
def settings() -> Settings:
    return Settings(
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
        PLATFORM_ADAPTER="telegram",
    )


@pytest.fixture()
def fake_chat() -> SimpleNamespace:
    return SimpleNamespace(id=101)


@pytest.fixture()
def fake_user() -> SimpleNamespace:
    return SimpleNamespace(id=202, username="tester")


@pytest.fixture()
def async_answer() -> AsyncMock:
    return AsyncMock()
