from __future__ import annotations

from reflebot_telegram_bot.backend.client import BackendApiClient
from reflebot_telegram_bot.backend.schemas import (
    ActionResponse,
    LoginRequest,
    MessageDeliveredRequest,
    LoginResponse,
    TextActionRequest,
)
from reflebot_telegram_bot.core.models import PlatformAttachment, PlatformIdentity
from reflebot_telegram_bot.core.ports import BackendIdentityMapper, BackendWorkflowPort


class BackendGateway(BackendWorkflowPort):
    def __init__(
        self,
        api_client: BackendApiClient,
        identity_mapper: BackendIdentityMapper,
    ) -> None:
        self._api_client = api_client
        self._identity_mapper = identity_mapper

    async def login(
        self,
        identity: PlatformIdentity,
        invite_token: str | None = None,
    ) -> LoginResponse:
        username = self._identity_mapper.login_username(identity)
        telegram_id = self._identity_mapper.platform_user_id(identity)
        payload = LoginRequest(
            telegram_id=telegram_id,
            invite_token=invite_token,
        ).model_dump(mode="json")
        data = await self._api_client.post_json(
            f"/auth/{username}/login",
            payload=payload,
        )
        return LoginResponse.model_validate(data)

    async def send_button(
        self,
        identity: PlatformIdentity,
        action: str,
    ) -> ActionResponse:
        data = await self._api_client.post_json(
            f"/actions/button/{action}",
            telegram_id=self._identity_mapper.platform_user_id(identity),
        )
        return ActionResponse.model_validate(data)

    async def send_text(
        self,
        identity: PlatformIdentity,
        text: str,
    ) -> ActionResponse:
        payload = TextActionRequest(text=text).model_dump(mode="json")
        data = await self._api_client.post_json(
            "/actions/text",
            payload=payload,
            telegram_id=self._identity_mapper.platform_user_id(identity),
        )
        return ActionResponse.model_validate(data)

    async def send_file(
        self,
        identity: PlatformIdentity,
        attachment: PlatformAttachment,
    ) -> ActionResponse:
        data, files = self._identity_mapper.attachment_payload(attachment)
        payload = await self._api_client.post_multipart(
            "/actions/file",
            data=data,
            files=files,
            telegram_id=self._identity_mapper.platform_user_id(identity),
        )
        return ActionResponse.model_validate(payload)

    async def notify_message_delivered(
        self,
        identity: PlatformIdentity,
        tracking_key: str,
        telegram_message_id: int,
    ) -> None:
        payload = MessageDeliveredRequest(
            tracking_key=tracking_key,
            telegram_message_id=telegram_message_id,
        ).model_dump(mode="json")
        await self._api_client.post_json(
            "/actions/message-delivered",
            payload=payload,
            telegram_id=self._identity_mapper.platform_user_id(identity),
        )
