from __future__ import annotations

import json
import logging

import aio_pika
from aio_pika import ExchangeType
from aio_pika.abc import (
    AbstractChannel,
    AbstractExchange,
    AbstractIncomingMessage,
    AbstractQueue,
    AbstractRobustConnection,
)
from pydantic import ValidationError

from reflebot_telegram_bot.broker.publisher import ReflectionPromptResultPublisher
from reflebot_telegram_bot.broker.schemas import (
    ReflectionPromptCommand,
    ReflectionPromptResultEvent,
    SendCourseMessageCommand,
    UpdateReflectionPromptCommand,
    reflection_prompt_command_adapter,
)
from reflebot_telegram_bot.core.use_cases.broker_prompt import BrokerPromptUseCase
from reflebot_telegram_bot.core.ports import PlatformSender
from reflebot_telegram_bot.settings import Settings

logger = logging.getLogger(__name__)


class ReflectionPromptConsumer:
    def __init__(
        self,
        *,
        settings: Settings,
        broker_prompt_use_case: BrokerPromptUseCase,
        platform_sender: PlatformSender,
    ) -> None:
        self._settings = settings
        self._broker_prompt_use_case = broker_prompt_use_case
        self._platform_sender = platform_sender
        self._connection: AbstractRobustConnection | None = None
        self._channel: AbstractChannel | None = None
        self._commands_exchange: AbstractExchange | None = None
        self._result_exchange: AbstractExchange | None = None
        self._queue: AbstractQueue | None = None
        self._consumer_tag: str | None = None
        self._result_publisher: ReflectionPromptResultPublisher | None = None

    async def start(self) -> None:
        logger.info(
            (
                "Starting RabbitMQ consumer queue=%s commands_exchange=%s "
                "routing_key=%s results_exchange=%s results_routing_key=%s"
            ),
            self._settings.rabbitmq_reflection_prompt_queue,
            self._settings.rabbitmq_notifications_exchange,
            self._settings.rabbitmq_reflection_prompt_routing_key,
            self._settings.rabbitmq_notification_results_exchange,
            self._settings.rabbitmq_delivery_result_routing_key,
        )
        self._connection = await aio_pika.connect_robust(self._settings.broker_url)
        self._channel = await self._connection.channel()
        await self._channel.set_qos(prefetch_count=10)
        self._commands_exchange = await self._channel.declare_exchange(
            self._settings.rabbitmq_notifications_exchange,
            ExchangeType.DIRECT,
            durable=True,
        )
        self._result_exchange = await self._channel.declare_exchange(
            self._settings.rabbitmq_notification_results_exchange,
            ExchangeType.DIRECT,
            durable=True,
        )
        self._queue = await self._channel.declare_queue(
            self._settings.rabbitmq_reflection_prompt_queue,
            durable=True,
        )
        await self._queue.bind(
            self._commands_exchange,
            routing_key=self._settings.rabbitmq_reflection_prompt_routing_key,
        )
        self._result_publisher = ReflectionPromptResultPublisher(
            settings=self._settings,
            result_exchange=self._result_exchange,
        )
        self._consumer_tag = await self._queue.consume(self.process_message)

    async def close(self) -> None:
        if self._queue and self._consumer_tag:
            await self._queue.cancel(self._consumer_tag)
            self._consumer_tag = None
        if self._channel is not None:
            await self._channel.close()
            self._channel = None
        self._commands_exchange = None
        self._result_exchange = None
        self._result_publisher = None
        if self._connection is not None:
            await self._connection.close()
            self._connection = None

    async def process_message(self, message: AbstractIncomingMessage) -> None:
        try:
            payload = json.loads(message.body.decode("utf-8"))
            command = reflection_prompt_command_adapter.validate_python(payload)
        except (json.JSONDecodeError, ValidationError):
            logger.exception("Invalid reflection prompt message")
            await message.reject(requeue=False)
            return

        logger.info(
            (
                "Received broker command event_type=%s delivery_id=%s telegram_id=%s "
                "student_id=%s course_id=%s lection_session_id=%s "
                "telegram_message_id=%s"
            ),
            command.event_type,
            getattr(command, "delivery_id", None),
            command.telegram_id,
            getattr(command, "student_id", None),
            getattr(command, "course_id", None),
            getattr(command, "lection_session_id", None),
            getattr(command, "telegram_message_id", None),
        )

        try:
            use_case_result = await self._broker_prompt_use_case.execute(command)
            if isinstance(command, UpdateReflectionPromptCommand):
                delivery_result = await self._platform_sender.edit_batch(
                    use_case_result.identity,
                    use_case_result.batch,
                )
            else:
                delivery_result = await self._platform_sender.send_batch(
                    use_case_result.identity,
                    use_case_result.batch,
                )
        except Exception as exc:
            if isinstance(command, SendCourseMessageCommand):
                logger.exception(
                    (
                        "Course message delivery failed telegram_id=%s student_id=%s "
                        "course_id=%s error=%s"
                    ),
                    command.telegram_id,
                    command.student_id,
                    command.course_id,
                    str(exc),
                )
                await message.ack()
            else:
                await self._handle_delivery_failure(
                    command=command,
                    message=message,
                    error=exc,
                )
            return

        if isinstance(command, SendCourseMessageCommand):
            logger.info(
                (
                    "Course message sent telegram_id=%s student_id=%s course_id=%s "
                    "telegram_message_id=%s"
                ),
                command.telegram_id,
                command.student_id,
                command.course_id,
                delivery_result.primary_message_id,
            )
            await message.ack()
            return

        result_event = ReflectionPromptResultEvent(
            delivery_id=command.delivery_id,
            success=True,
            sent_at=delivery_result.sent_at,
            telegram_message_id=(
                int(delivery_result.primary_message_id)
                if delivery_result.primary_message_id is not None
                else None
            ),
            error=None,
        )

        try:
            await self._publish_result(result_event)
        except Exception:
            logger.exception(
                (
                    "Failed to publish success result after Telegram prompt operation "
                    "delivery_id=%s telegram_id=%s student_id=%s course_id=%s "
                    "lection_session_id=%s telegram_message_id=%s event_type=%s; "
                    "acking to avoid duplicate prompt"
                ),
                command.delivery_id,
                command.telegram_id,
                getattr(command, "student_id", None),
                getattr(command, "course_id", None),
                getattr(command, "lection_session_id", None),
                delivery_result.primary_message_id,
                command.event_type,
            )
            await message.ack()
            return

        logger.info(
            (
                "Reflection prompt processed delivery_id=%s telegram_id=%s "
                "student_id=%s course_id=%s lection_session_id=%s "
                "success=%s telegram_message_id=%s event_type=%s"
            ),
            command.delivery_id,
            command.telegram_id,
            getattr(command, "student_id", None),
            getattr(command, "course_id", None),
            getattr(command, "lection_session_id", None),
            True,
            delivery_result.primary_message_id,
            command.event_type,
        )
        await message.ack()

    async def _handle_delivery_failure(
        self,
        *,
        command: ReflectionPromptCommand,
        message: AbstractIncomingMessage,
        error: Exception,
    ) -> None:
        logger.exception(
            (
                "Reflection prompt delivery failed delivery_id=%s telegram_id=%s "
                "student_id=%s course_id=%s lection_session_id=%s "
                "telegram_message_id=%s event_type=%s error=%s"
            ),
            command.delivery_id,
            command.telegram_id,
            getattr(command, "student_id", None),
            getattr(command, "course_id", None),
            getattr(command, "lection_session_id", None),
            getattr(command, "telegram_message_id", None),
            command.event_type,
            str(error),
        )

        result_event = ReflectionPromptResultEvent(
            delivery_id=command.delivery_id,
            success=False,
            sent_at=None,
            telegram_message_id=getattr(command, "telegram_message_id", None),
            error=str(error),
        )
        try:
            await self._publish_result(result_event)
        except Exception as publish_error:
            logger.exception(
                (
                    "Failed to publish failure result delivery_id=%s telegram_id=%s "
                    "student_id=%s course_id=%s lection_session_id=%s error=%s; "
                    "requeueing because prompt "
                    "was not delivered successfully event_type=%s "
                    "telegram_message_id=%s"
                ),
                command.delivery_id,
                command.telegram_id,
                getattr(command, "student_id", None),
                getattr(command, "course_id", None),
                getattr(command, "lection_session_id", None),
                str(publish_error),
                command.event_type,
                getattr(command, "telegram_message_id", None),
            )
            await message.nack(requeue=True)
            return

        logger.info(
            (
                "Published failure result delivery_id=%s telegram_id=%s "
                "student_id=%s course_id=%s lection_session_id=%s "
                "success=%s error=%s event_type=%s "
                "telegram_message_id=%s"
            ),
            command.delivery_id,
            command.telegram_id,
            getattr(command, "student_id", None),
            getattr(command, "course_id", None),
            getattr(command, "lection_session_id", None),
            False,
            str(error),
            command.event_type,
            getattr(command, "telegram_message_id", None),
        )
        await message.ack()

    async def _publish_result(self, result_event: ReflectionPromptResultEvent) -> None:
        if self._result_publisher is None:
            raise RuntimeError("RabbitMQ result publisher is not initialized.")
        await self._result_publisher.publish(result_event)
