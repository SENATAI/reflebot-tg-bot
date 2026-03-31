from __future__ import annotations

import json

import aio_pika
from aio_pika.abc import AbstractExchange

from reflebot_telegram_bot.broker.schemas import ReflectionPromptResultEvent
from reflebot_telegram_bot.settings import Settings


class ReflectionPromptResultPublisher:
    def __init__(
        self,
        *,
        settings: Settings,
        result_exchange: AbstractExchange,
    ) -> None:
        self._settings = settings
        self._result_exchange = result_exchange

    async def publish(self, event: ReflectionPromptResultEvent) -> None:
        message = aio_pika.Message(
            body=event.model_dump_json().encode("utf-8"),
            content_type="application/json",
            delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
        )
        await self._result_exchange.publish(
            message,
            routing_key=self._settings.rabbitmq_delivery_result_routing_key,
        )
