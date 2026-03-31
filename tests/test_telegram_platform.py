from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from reflebot_telegram_bot.api.errors import BackendTransportError
from reflebot_telegram_bot.core.models import PlatformButton, PlatformIdentity, PlatformMedia, PlatformMessage, PlatformMessageBatch, UseCaseResult
from reflebot_telegram_bot.core.planner import ResponsePlanner
from reflebot_telegram_bot.platforms.telegram.router import (
    handle_callback_query,
    handle_file_message,
    handle_start_message,
    handle_text_message,
    should_forward_text_message,
)
from reflebot_telegram_bot.platforms.telegram.sender import TelegramSender
from reflebot_telegram_bot.platforms.telegram.update_mapper import TelegramUpdateMapper


@pytest.mark.asyncio()
async def test_update_mapper_maps_callback_and_downloads_spreadsheet() -> None:
    async def write_binary(file_id: str, destination) -> None:
        assert file_id == "doc-id"
        destination.write(b"spreadsheet")

    bot = SimpleNamespace(download=AsyncMock(side_effect=write_binary))
    mapper = TelegramUpdateMapper(bot)
    callback = SimpleNamespace(
        id="cbq-id",
        data="next",
        from_user=SimpleNamespace(id=1, username="tester"),
        message=SimpleNamespace(message_id=22, chat=SimpleNamespace(id=33)),
    )
    document_message = SimpleNamespace(
        document=SimpleNamespace(
            file_id="doc-id",
            file_name="students.xlsx",
            mime_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        ),
        video=None,
        video_note=None,
        from_user=SimpleNamespace(id=1, username="tester"),
        chat=SimpleNamespace(id=33),
        message_id=44,
    )

    callback_update = await mapper.from_callback_query(callback)
    file_update = await mapper.from_file_message(document_message)

    assert callback_update.action == "next"
    assert callback_update.interaction_id == "cbq-id"
    assert file_update.attachment is not None
    assert file_update.attachment.kind == "binary_document"
    assert file_update.attachment.binary_content == b"spreadsheet"


@pytest.mark.asyncio()
async def test_update_mapper_extracts_start_payload() -> None:
    bot = SimpleNamespace(download=AsyncMock())
    mapper = TelegramUpdateMapper(bot)
    start_message = SimpleNamespace(
        text="/start invite-token-123",
        from_user=SimpleNamespace(id=1, username="tester"),
        chat=SimpleNamespace(id=33),
        message_id=44,
    )

    start_update = await mapper.from_start_message(start_message)

    assert start_update.kind == "start"
    assert start_update.start_payload == "invite-token-123"


@pytest.mark.asyncio()
async def test_update_mapper_extracts_start_payload_with_bot_username() -> None:
    bot = SimpleNamespace(download=AsyncMock())
    mapper = TelegramUpdateMapper(bot)
    start_message = SimpleNamespace(
        text="/start@reflobot_test_bot invite-token-456",
        from_user=SimpleNamespace(id=1, username="tester"),
        chat=SimpleNamespace(id=33),
        message_id=45,
    )

    start_update = await mapper.from_start_message(start_message)

    assert start_update.kind == "start"
    assert start_update.start_payload == "invite-token-456"


@pytest.mark.asyncio()
async def test_sender_sends_batch_with_edit_and_followups() -> None:
    bot = SimpleNamespace(
        edit_message_text=AsyncMock(return_value=SimpleNamespace(message_id=11)),
        send_message=AsyncMock(return_value=SimpleNamespace(message_id=12)),
        send_document=AsyncMock(),
        send_video=AsyncMock(),
        send_video_note=AsyncMock(),
        answer_callback_query=AsyncMock(),
        download=AsyncMock(),
    )
    sender = TelegramSender(bot)
    identity = PlatformIdentity(platform="telegram", user_id="1", chat_id="1")
    batch = PlatformMessageBatch(
        primary_message=PlatformMessage(
            text="Main",
            parse_mode="HTML",
            buttons=[PlatformButton(text="Next", action="next")],
            media=[PlatformMedia(kind="presentation", platform_file_ref="presentation-id")],
            edit_target_message_id="77",
        ),
        follow_up_messages=[
            PlatformMessage(
                text="Follow up",
                buttons=[PlatformButton(text="Menu", action="menu")],
                media=[PlatformMedia(kind="recording", platform_file_ref="video-id")],
            )
        ],
    )

    result = await sender.send_batch(identity, batch)
    await sender.answer_interaction("cbq-id")

    bot.edit_message_text.assert_awaited_once()
    assert bot.send_message.await_count == 1
    follow_up_call = bot.send_message.await_args_list[0]
    assert follow_up_call.kwargs["text"] == "Follow up"
    assert follow_up_call.kwargs["reply_markup"] is not None
    bot.send_document.assert_awaited_once()
    bot.send_video.assert_awaited_once()
    bot.answer_callback_query.assert_awaited_once()
    assert result.primary_message_id == "11"


@pytest.mark.asyncio()
async def test_router_wiring_calls_use_cases_and_sender(settings) -> None:
    bot = SimpleNamespace(download=AsyncMock())
    update_mapper = TelegramUpdateMapper(bot)
    sender = AsyncMock()
    planner = ResponsePlanner()
    use_case_result = UseCaseResult(
        identity=PlatformIdentity(platform="telegram", user_id="1", chat_id="1", username="tester"),
        batch=PlatformMessageBatch(primary_message=PlatformMessage(text="OK")),
    )
    start_use_case = AsyncMock()
    start_use_case.execute.return_value = use_case_result
    button_use_case = AsyncMock()
    button_use_case.execute.return_value = use_case_result
    text_use_case = AsyncMock()
    text_use_case.execute.return_value = use_case_result
    file_use_case = AsyncMock()
    file_use_case.execute.return_value = use_case_result

    start_message = SimpleNamespace(
        text="/start invite-token",
        from_user=SimpleNamespace(id=1, username="tester"),
        chat=SimpleNamespace(id=1),
        message_id=1,
    )
    callback = SimpleNamespace(
        id="cbq-id",
        data="next",
        from_user=SimpleNamespace(id=1, username="tester"),
        message=SimpleNamespace(message_id=2, chat=SimpleNamespace(id=1)),
    )
    text_message = SimpleNamespace(
        from_user=SimpleNamespace(id=1, username="tester"),
        chat=SimpleNamespace(id=1),
        message_id=3,
        text="hello",
    )
    file_message = SimpleNamespace(
        from_user=SimpleNamespace(id=1, username="tester"),
        chat=SimpleNamespace(id=1),
        message_id=4,
        document=None,
        video=None,
        video_note=SimpleNamespace(file_id="video-note-id"),
    )

    await handle_start_message(start_message, update_mapper, start_use_case, sender, planner, settings)
    await handle_callback_query(callback, update_mapper, button_use_case, sender, planner, settings)
    await handle_text_message(text_message, update_mapper, text_use_case, sender, planner, settings)
    await handle_file_message(file_message, update_mapper, file_use_case, sender, planner, settings)

    start_use_case.execute.assert_awaited_once()
    start_update = start_use_case.execute.await_args.args[0]
    assert start_update.start_payload == "invite-token"
    button_use_case.execute.assert_awaited_once()
    text_use_case.execute.assert_awaited_once()
    file_use_case.execute.assert_awaited_once()
    assert sender.send_batch.await_count == 4
    sender.answer_interaction.assert_awaited_once_with("cbq-id")


@pytest.mark.asyncio()
async def test_start_handler_logs_backend_error_with_invite_payload(settings, caplog) -> None:
    bot = SimpleNamespace(download=AsyncMock())
    update_mapper = TelegramUpdateMapper(bot)
    sender = AsyncMock()
    planner = ResponsePlanner()
    start_use_case = AsyncMock()
    start_use_case.execute.side_effect = BackendTransportError(
        status_code=400,
        detail="Invite token invalid",
        error_code="INVALID_INVITE_TOKEN",
        endpoint="/auth/tester/login",
    )
    start_message = SimpleNamespace(
        text="/start invite-token",
        from_user=SimpleNamespace(id=1, username="tester"),
        chat=SimpleNamespace(id=1),
        message_id=1,
    )

    with caplog.at_level("WARNING"):
        await handle_start_message(
            start_message,
            update_mapper,
            start_use_case,
            sender,
            planner,
            settings,
        )

    assert "Backend start/login request failed" in caplog.text
    record = next(record for record in caplog.records if record.message == "Backend start/login request failed")
    assert record.status_code == 400
    assert record.detail == "Invite token invalid"
    assert record.error_code == "INVALID_INVITE_TOKEN"
    assert record.has_invite_payload is True
    sender.send_batch.assert_awaited_once()


def test_should_forward_text_message_allows_join_course_commands() -> None:
    assert should_forward_text_message("join_course") is True
    assert should_forward_text_message("/join_course") is True
    assert should_forward_text_message("/join_course ABC123") is True
    assert should_forward_text_message("/join_course@reflobot_test_bot") is True


def test_should_forward_text_message_ignores_other_slash_commands() -> None:
    assert should_forward_text_message("/start") is False
    assert should_forward_text_message("/help") is False
    assert should_forward_text_message("/unknown value") is False
    assert should_forward_text_message(None) is False
