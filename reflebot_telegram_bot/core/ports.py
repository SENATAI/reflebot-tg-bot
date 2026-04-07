from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from reflebot_telegram_bot.api.schemas import ActionResponse, LoginResponse
from reflebot_telegram_bot.core.models import (
    PlatformAttachment,
    PlatformDeliveryResult,
    PlatformIdentity,
    PlatformMessageBatch,
)


@dataclass(frozen=True, slots=True)
class PlatformCapabilities:
    supports_message_edit: bool = False
    supports_inline_buttons: bool = False
    supports_platform_media_refs: bool = False
    supports_video_note: bool = False


class PlatformSender(Protocol):
    @property
    def platform_name(self) -> str: ...

    @property
    def capabilities(self) -> PlatformCapabilities: ...

    async def send_batch(
        self,
        identity: PlatformIdentity,
        batch: PlatformMessageBatch,
    ) -> PlatformDeliveryResult: ...

    async def edit_batch(
        self,
        identity: PlatformIdentity,
        batch: PlatformMessageBatch,
    ) -> PlatformDeliveryResult: ...

    async def answer_interaction(self, interaction_id: str | None) -> None: ...

    async def download_binary_attachment(self, file_ref: str) -> bytes: ...


class BackendIdentityMapper(Protocol):
    def login_username(self, identity: PlatformIdentity) -> str: ...

    def platform_user_id(self, identity: PlatformIdentity) -> int: ...

    def attachment_payload(
        self,
        attachment: PlatformAttachment,
    ) -> tuple[dict[str, object] | None, dict[str, object] | None]: ...


class BackendWorkflowPort(Protocol):
    async def login(
        self,
        identity: PlatformIdentity,
        invite_token: str | None = None,
    ) -> LoginResponse: ...

    async def send_button(
        self,
        identity: PlatformIdentity,
        action: str,
    ) -> ActionResponse: ...

    async def send_text(
        self,
        identity: PlatformIdentity,
        text: str,
    ) -> ActionResponse: ...

    async def send_file(
        self,
        identity: PlatformIdentity,
        attachment: PlatformAttachment,
    ) -> ActionResponse: ...

    async def notify_message_delivered(
        self,
        identity: PlatformIdentity,
        tracking_key: str,
        telegram_message_id: int,
    ) -> None: ...
