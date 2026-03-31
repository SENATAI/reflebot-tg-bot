from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal


@dataclass(slots=True)
class PlatformIdentity:
    platform: str
    user_id: str
    chat_id: str
    username: str | None = None


@dataclass(slots=True)
class PlatformAttachment:
    kind: Literal["binary_document", "platform_media"]
    filename: str | None = None
    mime_type: str | None = None
    binary_content: bytes | None = None
    platform_file_ref: str | None = None


@dataclass(slots=True)
class PlatformUpdate:
    kind: Literal["start", "button", "text", "file"]
    identity: PlatformIdentity
    action: str | None = None
    text: str | None = None
    start_payload: str | None = None
    attachment: PlatformAttachment | None = None
    source_message_id: str | None = None
    interaction_id: str | None = None


@dataclass(slots=True)
class PlatformButton:
    text: str
    action: str


@dataclass(slots=True)
class PlatformMedia:
    kind: str
    platform_file_ref: str | None = None
    binary_content: bytes | None = None
    filename: str | None = None


@dataclass(slots=True)
class PlatformMessage:
    text: str | None = None
    parse_mode: str | None = None
    buttons: list[PlatformButton] = field(default_factory=list)
    media: list[PlatformMedia] = field(default_factory=list)
    edit_target_message_id: str | None = None


@dataclass(slots=True)
class PlatformMessageBatch:
    primary_message: PlatformMessage
    follow_up_messages: list[PlatformMessage] = field(default_factory=list)


@dataclass(slots=True)
class PlatformDeliveryResult:
    primary_message_id: str | None = None
    sent_at: datetime | None = None


@dataclass(slots=True)
class UseCaseResult:
    identity: PlatformIdentity
    batch: PlatformMessageBatch
