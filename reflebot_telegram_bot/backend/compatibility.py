from __future__ import annotations

from dataclasses import dataclass

from reflebot_telegram_bot.core.models import PlatformAttachment, PlatformIdentity
from reflebot_telegram_bot.core.ports import BackendIdentityMapper


class MissingPlatformUsernameError(ValueError):
    """Raised when the current platform identity lacks a required username."""


@dataclass(slots=True)
class TelegramBackendIdentityMapper(BackendIdentityMapper):
    platform_name: str = "telegram"

    def login_username(self, identity: PlatformIdentity) -> str:
        if identity.platform != self.platform_name:
            raise ValueError(f"Unsupported platform: {identity.platform}")
        username = (identity.username or "").lstrip("@")
        if not username:
            raise MissingPlatformUsernameError("Telegram username is required.")
        return username

    def platform_user_id(self, identity: PlatformIdentity) -> int:
        if identity.platform != self.platform_name:
            raise ValueError(f"Unsupported platform: {identity.platform}")
        return int(identity.user_id)

    def attachment_payload(
        self,
        attachment: PlatformAttachment,
    ) -> tuple[dict[str, object] | None, dict[str, object] | None]:
        if attachment.kind == "binary_document":
            files = {
                "file": (
                    attachment.filename or "upload.bin",
                    attachment.binary_content or b"",
                    attachment.mime_type or "application/octet-stream",
                )
            }
            return None, files

        data = {"telegram_file_id": attachment.platform_file_ref or ""}
        return data, None
