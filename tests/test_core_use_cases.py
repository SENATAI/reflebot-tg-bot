from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from reflebot_telegram_bot.api.schemas import ActionResponse, BackendButton, BackendFile, DialogMessage, LoginResponse
from reflebot_telegram_bot.broker.schemas import ReflectionPromptCommand
from reflebot_telegram_bot.core.models import PlatformAttachment, PlatformIdentity, PlatformUpdate
from reflebot_telegram_bot.core.planner import ResponsePlanner
from reflebot_telegram_bot.core.use_cases.broker_prompt import BrokerPromptUseCase
from reflebot_telegram_bot.core.use_cases.button import ButtonUseCase
from reflebot_telegram_bot.core.use_cases.file import FileUseCase
from reflebot_telegram_bot.core.use_cases.start import StartUseCase
from reflebot_telegram_bot.core.use_cases.text import TextUseCase


def make_action_response() -> ActionResponse:
    return ActionResponse(
        message="Экран",
        parse_mode="HTML",
        buttons=[
            BackendButton(text="Дальше", action="next"),
            BackendButton(text="Тех. поддержка", url="https://t.me/kartbllansh"),
        ],
        files=[BackendFile(telegram_file_id="presentation-id", kind="presentation")],
        dialog_messages=[
            DialogMessage(
                message="Follow up",
                parse_mode="HTML",
                buttons=[
                    BackendButton(text="Меню", action="menu"),
                    BackendButton(text="Тех. поддержка", url="https://t.me/kartbllansh"),
                ],
                files=[BackendFile(telegram_file_id="recording-id", kind="recording")],
            )
        ],
    )


def test_planner_maps_backend_response_to_platform_batch() -> None:
    planner = ResponsePlanner()
    batch = planner.from_backend_response(make_action_response(), edit_target_message_id="77")

    assert batch.primary_message.text == "Экран"
    assert batch.primary_message.edit_target_message_id == "77"
    assert batch.primary_message.buttons[0].action == "next"
    assert batch.primary_message.buttons[1].url == "https://t.me/kartbllansh"
    assert batch.primary_message.media[0].platform_file_ref == "presentation-id"
    assert batch.follow_up_messages[0].text == "Follow up"
    assert batch.follow_up_messages[0].buttons[0].action == "menu"
    assert batch.follow_up_messages[0].buttons[1].url == "https://t.me/kartbllansh"
    assert batch.follow_up_messages[0].media[0].kind == "recording"


@pytest.mark.asyncio()
async def test_start_use_case_calls_backend_workflow() -> None:
    backend_workflow = AsyncMock()
    backend_workflow.login.return_value = LoginResponse(message="Привет")
    use_case = StartUseCase(backend_workflow, ResponsePlanner())
    update = PlatformUpdate(
        kind="start",
        identity=PlatformIdentity(platform="telegram", user_id="1", chat_id="1", username="tester"),
        start_payload="invite-token",
    )

    result = await use_case.execute(update)

    backend_workflow.login.assert_awaited_once_with(update.identity, invite_token="invite-token")
    assert result.batch.primary_message.text == "Привет"


@pytest.mark.asyncio()
async def test_button_text_and_file_use_cases_use_backend_workflow() -> None:
    backend_workflow = AsyncMock()
    backend_workflow.send_button.return_value = make_action_response()
    backend_workflow.send_text.return_value = make_action_response()
    backend_workflow.send_file.return_value = make_action_response()
    planner = ResponsePlanner()

    button_result = await ButtonUseCase(backend_workflow, planner).execute(
        PlatformUpdate(
            kind="button",
            identity=PlatformIdentity(platform="telegram", user_id="2", chat_id="2"),
            action="next",
            source_message_id="99",
        )
    )
    text_result = await TextUseCase(backend_workflow, planner).execute(
        PlatformUpdate(
            kind="text",
            identity=PlatformIdentity(platform="telegram", user_id="2", chat_id="2"),
            text="hello",
        )
    )
    file_result = await FileUseCase(backend_workflow, planner).execute(
        PlatformUpdate(
            kind="file",
            identity=PlatformIdentity(platform="telegram", user_id="2", chat_id="2"),
            attachment=PlatformAttachment(kind="platform_media", platform_file_ref="file-id"),
        )
    )

    assert button_result.batch.primary_message.edit_target_message_id == "99"
    assert text_result.batch.primary_message.text == "Экран"
    assert file_result.batch.primary_message.media[0].platform_file_ref == "presentation-id"


@pytest.mark.asyncio()
async def test_broker_prompt_use_case_builds_platform_identity_and_batch() -> None:
    command = ReflectionPromptCommand.model_validate(
        {
            "event_type": "send_reflection_prompt",
            "delivery_id": "00000000-0000-0000-0000-000000000001",
            "student_id": "00000000-0000-0000-0000-000000000002",
            "telegram_id": 123,
            "lection_session_id": "00000000-0000-0000-0000-000000000003",
            "message_text": "Prompt",
            "parse_mode": "HTML",
            "buttons": [{"text": "Go", "action": "start"}],
            "scheduled_for": "2026-03-29T10:49:01+00:00",
        }
    )

    result = await BrokerPromptUseCase(ResponsePlanner(), platform_name="telegram").execute(command)

    assert result.identity.platform == "telegram"
    assert result.identity.chat_id == "123"
    assert result.batch.primary_message.buttons[0].action == "start"
