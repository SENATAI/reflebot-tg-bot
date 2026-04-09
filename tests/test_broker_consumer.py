from __future__ import annotations

import json
from datetime import UTC, datetime
from uuid import uuid4
from unittest.mock import AsyncMock

import pytest

from reflebot_telegram_bot.broker.consumer import ReflectionPromptConsumer
from reflebot_telegram_bot.broker.schemas import ReflectionPromptResultEvent
from reflebot_telegram_bot.core.models import PlatformDeliveryResult, PlatformIdentity, PlatformMessage, PlatformMessageBatch, UseCaseResult


class FakeIncomingMessage:
    def __init__(self, body: bytes) -> None:
        self.body = body
        self.ack = AsyncMock()
        self.nack = AsyncMock()
        self.reject = AsyncMock()


def make_prompt_payload() -> dict[str, object]:
    return {
        "event_type": "send_reflection_prompt",
        "delivery_id": str(uuid4()),
        "student_id": str(uuid4()),
        "telegram_id": 10,
        "lection_session_id": str(uuid4()),
        "message_text": "Пора записать рефлексию",
        "parse_mode": "HTML",
        "buttons": [
            {
                "text": "Записать",
                "action": "student_start_reflection:1",
            }
        ],
        "scheduled_for": "2026-03-29T10:49:01+00:00",
    }


def make_update_payload() -> dict[str, object]:
    return {
        "event_type": "update_reflection_prompt",
        "delivery_id": str(uuid4()),
        "telegram_id": 10,
        "telegram_message_id": 456,
        "lection_session_id": str(uuid4()),
        "message_text": "Дедлайн истек",
        "parse_mode": "HTML",
        "buttons": [
            {
                "text": "Тех. поддержка",
                "url": "https://t.me/kartbllansh",
            }
        ],
    }


def make_course_message_payload() -> dict[str, object]:
    return {
        "event_type": "send_course_message",
        "course_id": str(uuid4()),
        "student_id": str(uuid4()),
        "telegram_id": 10,
        "message_text": "Текст сообщения студенту",
        "parse_mode": "HTML",
        "buttons": [
            {
                "text": "Тех. поддержка",
                "url": "https://t.me/kartbllansh",
            }
        ],
    }


def make_use_case_result() -> UseCaseResult:
    return UseCaseResult(
        identity=PlatformIdentity(platform="telegram", user_id="10", chat_id="10"),
        batch=PlatformMessageBatch(primary_message=PlatformMessage(text="Prompt")),
    )


@pytest.mark.asyncio()
async def test_consumer_declares_and_binds_topology(settings) -> None:
    broker_prompt_use_case = AsyncMock()
    platform_sender = AsyncMock()
    consumer = ReflectionPromptConsumer(
        settings=settings,
        broker_prompt_use_case=broker_prompt_use_case,
        platform_sender=platform_sender,
    )
    queue = AsyncMock()
    commands_exchange = AsyncMock()
    results_exchange = AsyncMock()
    channel = AsyncMock()
    channel.declare_exchange = AsyncMock(side_effect=[commands_exchange, results_exchange])
    channel.declare_queue = AsyncMock(return_value=queue)
    connection = AsyncMock()
    connection.channel = AsyncMock(return_value=channel)

    from reflebot_telegram_bot.broker import consumer as consumer_module

    original_connect = consumer_module.aio_pika.connect_robust
    consumer_module.aio_pika.connect_robust = AsyncMock(return_value=connection)
    try:
        await consumer.start()
    finally:
        consumer_module.aio_pika.connect_robust = original_connect

    channel.declare_queue.assert_awaited_once_with("bot.reflection-prompts", durable=True)
    queue.bind.assert_awaited_once_with(commands_exchange, routing_key="reflection_prompt.send")
    queue.consume.assert_awaited_once()


@pytest.mark.asyncio()
async def test_consumer_acks_valid_message_and_publishes_success_result(settings) -> None:
    broker_prompt_use_case = AsyncMock()
    broker_prompt_use_case.execute.return_value = make_use_case_result()
    platform_sender = AsyncMock()
    platform_sender.send_batch.return_value = PlatformDeliveryResult(
        primary_message_id="123",
        sent_at=datetime(2026, 3, 29, 10, 49, 30, tzinfo=UTC),
    )
    consumer = ReflectionPromptConsumer(
        settings=settings,
        broker_prompt_use_case=broker_prompt_use_case,
        platform_sender=platform_sender,
    )
    consumer._result_publisher = AsyncMock()
    message = FakeIncomingMessage(json.dumps(make_prompt_payload()).encode("utf-8"))

    await consumer.process_message(message)

    broker_prompt_use_case.execute.assert_awaited_once()
    platform_sender.send_batch.assert_awaited_once()
    consumer._result_publisher.publish.assert_awaited_once()
    published_event = consumer._result_publisher.publish.await_args.args[0]
    assert isinstance(published_event, ReflectionPromptResultEvent)
    assert published_event.success is True
    assert published_event.telegram_message_id == 123
    message.ack.assert_awaited_once()
    message.nack.assert_not_awaited()
    message.reject.assert_not_awaited()


@pytest.mark.asyncio()
async def test_consumer_acks_when_success_result_publish_fails_to_avoid_duplicate_prompt(
    settings,
) -> None:
    broker_prompt_use_case = AsyncMock()
    broker_prompt_use_case.execute.return_value = make_use_case_result()
    platform_sender = AsyncMock()
    platform_sender.send_batch.return_value = PlatformDeliveryResult(
        primary_message_id="123",
        sent_at=datetime(2026, 3, 29, 10, 49, 30, tzinfo=UTC),
    )
    consumer = ReflectionPromptConsumer(
        settings=settings,
        broker_prompt_use_case=broker_prompt_use_case,
        platform_sender=platform_sender,
    )
    consumer._result_publisher = AsyncMock()
    consumer._result_publisher.publish.side_effect = RuntimeError("publish failed")
    message = FakeIncomingMessage(json.dumps(make_prompt_payload()).encode("utf-8"))

    await consumer.process_message(message)

    message.ack.assert_awaited_once()
    message.nack.assert_not_awaited()


@pytest.mark.asyncio()
async def test_consumer_rejects_invalid_payload(settings) -> None:
    broker_prompt_use_case = AsyncMock()
    platform_sender = AsyncMock()
    consumer = ReflectionPromptConsumer(
        settings=settings,
        broker_prompt_use_case=broker_prompt_use_case,
        platform_sender=platform_sender,
    )
    consumer._result_publisher = AsyncMock()
    message = FakeIncomingMessage(b'{"event_type": "send_reflection_prompt"}')

    await consumer.process_message(message)

    message.reject.assert_awaited_once_with(requeue=False)
    message.ack.assert_not_awaited()
    consumer._result_publisher.publish.assert_not_awaited()


@pytest.mark.asyncio()
async def test_consumer_acks_failure_and_publishes_failure_result(settings) -> None:
    broker_prompt_use_case = AsyncMock()
    broker_prompt_use_case.execute.return_value = make_use_case_result()
    platform_sender = AsyncMock()
    platform_sender.send_batch.side_effect = RuntimeError("telegram send failed")
    consumer = ReflectionPromptConsumer(
        settings=settings,
        broker_prompt_use_case=broker_prompt_use_case,
        platform_sender=platform_sender,
    )
    consumer._result_publisher = AsyncMock()
    message = FakeIncomingMessage(json.dumps(make_prompt_payload()).encode("utf-8"))

    await consumer.process_message(message)

    consumer._result_publisher.publish.assert_awaited_once()
    published_event = consumer._result_publisher.publish.await_args.args[0]
    assert published_event.success is False
    assert published_event.error == "telegram send failed"
    message.ack.assert_awaited_once()
    message.nack.assert_not_awaited()


@pytest.mark.asyncio()
async def test_consumer_requeues_when_failure_result_publish_fails(settings) -> None:
    broker_prompt_use_case = AsyncMock()
    broker_prompt_use_case.execute.return_value = make_use_case_result()
    platform_sender = AsyncMock()
    platform_sender.send_batch.side_effect = RuntimeError("telegram send failed")
    consumer = ReflectionPromptConsumer(
        settings=settings,
        broker_prompt_use_case=broker_prompt_use_case,
        platform_sender=platform_sender,
    )
    consumer._result_publisher = AsyncMock()
    consumer._result_publisher.publish.side_effect = RuntimeError("publish failed")
    message = FakeIncomingMessage(json.dumps(make_prompt_payload()).encode("utf-8"))

    await consumer.process_message(message)

    message.nack.assert_awaited_once_with(requeue=True)
    message.ack.assert_not_awaited()


@pytest.mark.asyncio()
async def test_consumer_edits_existing_message_for_update_prompt(settings) -> None:
    broker_prompt_use_case = AsyncMock()
    broker_prompt_use_case.execute.return_value = make_use_case_result()
    platform_sender = AsyncMock()
    platform_sender.edit_batch.return_value = PlatformDeliveryResult(
        primary_message_id="456",
        sent_at=datetime(2026, 4, 6, 21, 30, 0, tzinfo=UTC),
    )
    consumer = ReflectionPromptConsumer(
        settings=settings,
        broker_prompt_use_case=broker_prompt_use_case,
        platform_sender=platform_sender,
    )
    consumer._result_publisher = AsyncMock()
    message = FakeIncomingMessage(json.dumps(make_update_payload()).encode("utf-8"))

    await consumer.process_message(message)

    platform_sender.edit_batch.assert_awaited_once()
    platform_sender.send_batch.assert_not_called()
    published_event = consumer._result_publisher.publish.await_args.args[0]
    assert published_event.success is True
    assert published_event.telegram_message_id == 456
    message.ack.assert_awaited_once()


@pytest.mark.asyncio()
async def test_consumer_publishes_failure_result_for_update_prompt_edit_error(settings) -> None:
    broker_prompt_use_case = AsyncMock()
    broker_prompt_use_case.execute.return_value = make_use_case_result()
    platform_sender = AsyncMock()
    platform_sender.edit_batch.side_effect = RuntimeError("telegram edit failed")
    consumer = ReflectionPromptConsumer(
        settings=settings,
        broker_prompt_use_case=broker_prompt_use_case,
        platform_sender=platform_sender,
    )
    consumer._result_publisher = AsyncMock()
    message = FakeIncomingMessage(json.dumps(make_update_payload()).encode("utf-8"))

    await consumer.process_message(message)

    published_event = consumer._result_publisher.publish.await_args.args[0]
    assert published_event.success is False
    assert published_event.telegram_message_id == 456
    assert published_event.error == "telegram edit failed"
    message.ack.assert_awaited_once()


@pytest.mark.asyncio()
async def test_consumer_sends_course_message_and_acks_without_publishing_result(settings) -> None:
    broker_prompt_use_case = AsyncMock()
    broker_prompt_use_case.execute.return_value = make_use_case_result()
    platform_sender = AsyncMock()
    platform_sender.send_batch.return_value = PlatformDeliveryResult(
        primary_message_id="789",
        sent_at=datetime(2026, 4, 9, 10, 0, 0, tzinfo=UTC),
    )
    consumer = ReflectionPromptConsumer(
        settings=settings,
        broker_prompt_use_case=broker_prompt_use_case,
        platform_sender=platform_sender,
    )
    consumer._result_publisher = AsyncMock()
    message = FakeIncomingMessage(json.dumps(make_course_message_payload()).encode("utf-8"))

    await consumer.process_message(message)

    platform_sender.send_batch.assert_awaited_once()
    platform_sender.edit_batch.assert_not_called()
    consumer._result_publisher.publish.assert_not_awaited()
    message.ack.assert_awaited_once()
    message.nack.assert_not_awaited()


@pytest.mark.asyncio()
async def test_consumer_acks_course_message_failure_without_result_publish(settings) -> None:
    broker_prompt_use_case = AsyncMock()
    broker_prompt_use_case.execute.return_value = make_use_case_result()
    platform_sender = AsyncMock()
    platform_sender.send_batch.side_effect = RuntimeError("telegram send failed")
    consumer = ReflectionPromptConsumer(
        settings=settings,
        broker_prompt_use_case=broker_prompt_use_case,
        platform_sender=platform_sender,
    )
    consumer._result_publisher = AsyncMock()
    message = FakeIncomingMessage(json.dumps(make_course_message_payload()).encode("utf-8"))

    await consumer.process_message(message)

    consumer._result_publisher.publish.assert_not_awaited()
    message.ack.assert_awaited_once()
    message.nack.assert_not_awaited()
