from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from reflebot_telegram_bot.backend.compatibility import MissingPlatformUsernameError, TelegramBackendIdentityMapper
from reflebot_telegram_bot.backend.gateway import BackendGateway
from reflebot_telegram_bot.core.models import PlatformAttachment, PlatformIdentity


def test_identity_mapper_strips_username_and_maps_attachment_payload() -> None:
    mapper = TelegramBackendIdentityMapper()
    identity = PlatformIdentity(platform="telegram", user_id="42", chat_id="42", username="@tester")

    assert mapper.login_username(identity) == "tester"
    assert mapper.platform_user_id(identity) == 42

    data, files = mapper.attachment_payload(
        PlatformAttachment(
            kind="binary_document",
            filename="students.xlsx",
            mime_type="application/octet-stream",
            binary_content=b"file",
        )
    )
    assert data is None
    assert files is not None

    data, files = mapper.attachment_payload(
        PlatformAttachment(kind="platform_media", platform_file_ref="file-id")
    )
    assert data == {"telegram_file_id": "file-id"}
    assert files is None


def test_identity_mapper_requires_username() -> None:
    mapper = TelegramBackendIdentityMapper()
    identity = PlatformIdentity(platform="telegram", user_id="42", chat_id="42", username=None)

    with pytest.raises(MissingPlatformUsernameError):
        mapper.login_username(identity)


@pytest.mark.asyncio()
async def test_backend_gateway_uses_compatibility_mapping_for_all_actions() -> None:
    api_client = AsyncMock()
    mapper = TelegramBackendIdentityMapper()
    gateway = BackendGateway(api_client, mapper)
    identity = PlatformIdentity(platform="telegram", user_id="42", chat_id="42", username="@tester")
    api_client.post_json.side_effect = [
        {"message": "Login"},
        {"message": "Button"},
        {"message": "Text"},
        {},
    ]
    api_client.post_multipart.return_value = {"message": "File"}

    await gateway.login(identity, invite_token="invite-token")
    await gateway.send_button(identity, "next")
    await gateway.send_text(identity, "hello")
    await gateway.send_file(
        identity,
        PlatformAttachment(kind="platform_media", platform_file_ref="video-id"),
    )
    await gateway.notify_message_delivered(
        identity,
        "reflection_status:123",
        456,
    )

    assert api_client.post_json.await_args_list[0].args[0] == "/auth/tester/login"
    assert api_client.post_json.await_args_list[0].kwargs["payload"] == {
        "telegram_id": 42,
        "invite_token": "invite-token",
    }
    assert api_client.post_json.await_args_list[1].args[0] == "/actions/button/next"
    assert api_client.post_json.await_args_list[2].args[0] == "/actions/text"
    assert api_client.post_json.await_args_list[3].args[0] == "/actions/message-delivered"
    assert api_client.post_json.await_args_list[3].kwargs["payload"] == {
        "tracking_key": "reflection_status:123",
        "telegram_message_id": 456,
    }
    assert api_client.post_json.await_args_list[3].kwargs["telegram_id"] == 42
    api_client.post_multipart.assert_awaited_once()
