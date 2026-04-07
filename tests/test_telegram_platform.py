from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from aiogram.exceptions import TelegramBadRequest

from reflebot_telegram_bot.api.errors import BackendTransportError
from reflebot_telegram_bot.platforms.telegram.commands import build_menu_commands, register_menu_commands
from reflebot_telegram_bot.core.models import PlatformButton, PlatformIdentity, PlatformMedia, PlatformMessage, PlatformMessageBatch, UseCaseResult
from reflebot_telegram_bot.core.planner import ResponsePlanner
from reflebot_telegram_bot.platforms.telegram.router import (
    handle_callback_query,
    handle_file_message,
    handle_start_message,
    handle_support_message,
    handle_text_message,
    should_forward_text_message,
    SUPPORT_BUTTON_TEXT,
    SUPPORT_MESSAGE,
    SUPPORT_URL,
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
            buttons=[
                PlatformButton(text="Next", action="next"),
                PlatformButton(text="Support", url="https://t.me/kartbllansh"),
            ],
            media=[PlatformMedia(kind="presentation", platform_file_ref="presentation-id")],
            edit_target_message_id="77",
        ),
        follow_up_messages=[
            PlatformMessage(
                text="Follow up",
                buttons=[
                    PlatformButton(text="Menu", action="menu"),
                    PlatformButton(text="Support", url="https://t.me/kartbllansh"),
                ],
                media=[PlatformMedia(kind="recording", platform_file_ref="video-id")],
            )
        ],
    )

    result = await sender.send_batch(identity, batch)
    await sender.answer_interaction("cbq-id")

    bot.edit_message_text.assert_awaited_once()
    primary_keyboard = bot.edit_message_text.await_args.kwargs["reply_markup"]
    assert primary_keyboard.inline_keyboard[0][0].callback_data == "next"
    assert primary_keyboard.inline_keyboard[1][0].url == "https://t.me/kartbllansh"
    assert bot.send_message.await_count == 1
    follow_up_call = bot.send_message.await_args_list[0]
    assert follow_up_call.kwargs["text"] == "Follow up"
    assert follow_up_call.kwargs["reply_markup"] is not None
    follow_up_keyboard = follow_up_call.kwargs["reply_markup"]
    assert follow_up_keyboard.inline_keyboard[0][0].callback_data == "menu"
    assert follow_up_keyboard.inline_keyboard[1][0].url == "https://t.me/kartbllansh"
    bot.send_document.assert_awaited_once()
    bot.send_video.assert_awaited_once()
    bot.answer_callback_query.assert_awaited_once()
    assert result.primary_message_id == "11"


@pytest.mark.asyncio()
async def test_sender_edits_existing_message_without_fallback_send() -> None:
    bot = SimpleNamespace(
        edit_message_text=AsyncMock(return_value=SimpleNamespace(message_id=456)),
        send_message=AsyncMock(),
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
            text="Updated",
            parse_mode="HTML",
            buttons=[PlatformButton(text="Support", url="https://t.me/kartbllansh")],
            edit_target_message_id="456",
        )
    )

    result = await sender.edit_batch(identity, batch)

    bot.edit_message_text.assert_awaited_once()
    bot.send_message.assert_not_awaited()
    assert result.primary_message_id == "456"


@pytest.mark.asyncio()
async def test_sender_treats_message_not_modified_as_success_for_edit_batch() -> None:
    bot = SimpleNamespace(
        edit_message_text=AsyncMock(
            side_effect=TelegramBadRequest(SimpleNamespace(), "Bad Request: message is not modified")
        ),
        send_message=AsyncMock(),
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
            text="Updated",
            edit_target_message_id="456",
        )
    )

    result = await sender.edit_batch(identity, batch)

    bot.send_message.assert_not_awaited()
    assert result.primary_message_id == "456"


@pytest.mark.asyncio()
async def test_router_wiring_calls_use_cases_and_sender(settings) -> None:
    bot = SimpleNamespace(download=AsyncMock())
    update_mapper = TelegramUpdateMapper(bot)
    backend_workflow = AsyncMock()
    sender = AsyncMock()
    planner = ResponsePlanner()
    use_case_result = UseCaseResult(
        identity=PlatformIdentity(platform="telegram", user_id="1", chat_id="1", username="tester"),
        batch=PlatformMessageBatch(
            primary_message=PlatformMessage(text="OK"),
            primary_message_tracking_key="reflection_status:123",
        ),
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

    sender.send_batch.return_value = SimpleNamespace(primary_message_id="321", sent_at=None)

    await handle_start_message(
        start_message, update_mapper, backend_workflow, start_use_case, sender, planner, settings
    )
    await handle_callback_query(
        callback, update_mapper, backend_workflow, button_use_case, sender, planner, settings
    )
    await handle_text_message(
        text_message, update_mapper, backend_workflow, text_use_case, sender, planner, settings
    )
    await handle_file_message(
        file_message, update_mapper, backend_workflow, file_use_case, sender, planner, settings
    )

    start_use_case.execute.assert_awaited_once()
    start_update = start_use_case.execute.await_args.args[0]
    assert start_update.start_payload == "invite-token"
    button_use_case.execute.assert_awaited_once()
    text_use_case.execute.assert_awaited_once()
    file_use_case.execute.assert_awaited_once()
    assert sender.send_batch.await_count == 4
    sender.answer_interaction.assert_awaited_once_with("cbq-id")
    assert backend_workflow.notify_message_delivered.await_count == 4


@pytest.mark.asyncio()
async def test_start_handler_logs_backend_error_with_invite_payload(settings, caplog) -> None:
    bot = SimpleNamespace(download=AsyncMock())
    update_mapper = TelegramUpdateMapper(bot)
    backend_workflow = AsyncMock()
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
            backend_workflow,
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


@pytest.mark.asyncio()
async def test_support_handler_sends_local_support_button() -> None:
    bot = SimpleNamespace(download=AsyncMock())
    update_mapper = TelegramUpdateMapper(bot)
    sender = AsyncMock()
    message = SimpleNamespace(
        from_user=SimpleNamespace(id=1, username="tester"),
        chat=SimpleNamespace(id=1),
        message_id=5,
    )

    await handle_support_message(message, update_mapper, sender)

    sender.send_batch.assert_awaited_once()
    identity, batch = sender.send_batch.await_args.args
    assert identity.chat_id == "1"
    assert batch.primary_message.text == SUPPORT_MESSAGE
    assert batch.primary_message.buttons[0].text == SUPPORT_BUTTON_TEXT
    assert batch.primary_message.buttons[0].url == SUPPORT_URL


@pytest.mark.asyncio()
async def test_router_notifies_backend_when_primary_message_has_tracking(settings) -> None:
    bot = SimpleNamespace(download=AsyncMock())
    update_mapper = TelegramUpdateMapper(bot)
    backend_workflow = AsyncMock()
    sender = AsyncMock()
    planner = ResponsePlanner()
    start_use_case = AsyncMock()
    start_use_case.execute.return_value = UseCaseResult(
        identity=PlatformIdentity(platform="telegram", user_id="1", chat_id="1", username="tester"),
        batch=PlatformMessageBatch(
            primary_message=PlatformMessage(text="Tracked"),
            primary_message_tracking_key="reflection_status:tracked",
        ),
    )
    sender.send_batch.return_value = SimpleNamespace(primary_message_id="456", sent_at=None)
    start_message = SimpleNamespace(
        text="/start",
        from_user=SimpleNamespace(id=1, username="tester"),
        chat=SimpleNamespace(id=1),
        message_id=1,
    )

    await handle_start_message(
        start_message,
        update_mapper,
        backend_workflow,
        start_use_case,
        sender,
        planner,
        settings,
    )

    backend_workflow.notify_message_delivered.assert_awaited_once_with(
        start_use_case.execute.return_value.identity,
        "reflection_status:tracked",
        456,
    )


@pytest.mark.asyncio()
async def test_router_logs_tracking_notification_error_but_keeps_user_delivery(
    settings,
    caplog,
) -> None:
    bot = SimpleNamespace(download=AsyncMock())
    update_mapper = TelegramUpdateMapper(bot)
    backend_workflow = AsyncMock()
    backend_workflow.notify_message_delivered.side_effect = BackendTransportError(
        status_code=500,
        detail="backend failed",
        error_code="TRACKING_FAILED",
        endpoint="/actions/message-delivered",
    )
    sender = AsyncMock()
    planner = ResponsePlanner()
    start_use_case = AsyncMock()
    start_use_case.execute.return_value = UseCaseResult(
        identity=PlatformIdentity(platform="telegram", user_id="1", chat_id="1", username="tester"),
        batch=PlatformMessageBatch(
            primary_message=PlatformMessage(text="Tracked"),
            primary_message_tracking_key="reflection_status:tracked",
        ),
    )
    sender.send_batch.return_value = SimpleNamespace(primary_message_id="456", sent_at=None)
    start_message = SimpleNamespace(
        text="/start",
        from_user=SimpleNamespace(id=1, username="tester"),
        chat=SimpleNamespace(id=1),
        message_id=1,
    )

    with caplog.at_level("WARNING"):
        await handle_start_message(
            start_message,
            update_mapper,
            backend_workflow,
            start_use_case,
            sender,
            planner,
            settings,
        )

    assert "Failed to notify backend about delivered message" in caplog.text
    sender.send_batch.assert_awaited_once()


@pytest.mark.asyncio()
async def test_register_menu_commands_sets_expected_commands() -> None:
    bot = SimpleNamespace(set_my_commands=AsyncMock())

    await register_menu_commands(bot)

    bot.set_my_commands.assert_awaited_once()
    commands = bot.set_my_commands.await_args.args[0]
    assert [(command.command, command.description) for command in commands] == [
        ("start", "Главное меню"),
        ("join_course", "Записаться на курс"),
        ("support", "Тех. поддержка"),
    ]


def test_should_forward_text_message_allows_join_course_commands() -> None:
    assert should_forward_text_message("join_course") is True
    assert should_forward_text_message("/join_course") is True
    assert should_forward_text_message("/join_course ABC123") is True
    assert should_forward_text_message("/join_course@reflobot_test_bot") is True


def test_should_forward_text_message_ignores_other_slash_commands() -> None:
    assert should_forward_text_message("/start") is False
    assert should_forward_text_message("/support") is False
    assert should_forward_text_message("/help") is False
    assert should_forward_text_message("/unknown value") is False
    assert should_forward_text_message(None) is False


def test_build_menu_commands_returns_expected_commands() -> None:
    commands = build_menu_commands()

    assert [(command.command, command.description) for command in commands] == [
        ("start", "Главное меню"),
        ("join_course", "Записаться на курс"),
        ("support", "Тех. поддержка"),
    ]
