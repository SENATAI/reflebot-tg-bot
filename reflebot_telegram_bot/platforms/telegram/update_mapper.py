from __future__ import annotations

from io import BytesIO
from pathlib import Path

from aiogram import Bot
from aiogram.types import CallbackQuery, Message

from reflebot_telegram_bot.core.models import PlatformAttachment, PlatformIdentity, PlatformUpdate


class UnsupportedTelegramUpdateError(ValueError):
    """Raised when the Telegram update cannot be mapped to a platform update."""


class TelegramUpdateMapper:
    _binary_extensions = {".xlsx", ".csv"}

    def __init__(self, bot: Bot) -> None:
        self._bot = bot

    async def from_start_message(self, message: Message) -> PlatformUpdate:
        return PlatformUpdate(
            kind="start",
            identity=self._identity_from_message(message),
            start_payload=self._extract_start_payload(message.text),
            source_message_id=str(message.message_id),
        )

    async def from_callback_query(self, callback: CallbackQuery) -> PlatformUpdate:
        if callback.data is None:
            raise UnsupportedTelegramUpdateError("Callback query has no action.")

        message = callback.message
        source_message_id = None
        chat_id = str(callback.from_user.id)
        if message is not None:
            source_message_id = str(message.message_id)
            chat_id = str(message.chat.id)

        identity = PlatformIdentity(
            platform="telegram",
            user_id=str(callback.from_user.id),
            chat_id=chat_id,
            username=callback.from_user.username,
        )
        return PlatformUpdate(
            kind="button",
            identity=identity,
            action=callback.data,
            source_message_id=source_message_id,
            interaction_id=callback.id,
        )

    async def from_text_message(self, message: Message) -> PlatformUpdate:
        return PlatformUpdate(
            kind="text",
            identity=self._identity_from_message(message),
            text=message.text,
            source_message_id=str(message.message_id),
        )

    async def from_file_message(self, message: Message) -> PlatformUpdate:
        attachment = await self._map_attachment(message)
        return PlatformUpdate(
            kind="file",
            identity=self._identity_from_message(message),
            attachment=attachment,
            source_message_id=str(message.message_id),
        )

    def _identity_from_message(self, message: Message) -> PlatformIdentity:
        if message.from_user is None:
            raise UnsupportedTelegramUpdateError("Telegram message has no sender.")

        return PlatformIdentity(
            platform="telegram",
            user_id=str(message.from_user.id),
            chat_id=str(message.chat.id),
            username=message.from_user.username,
        )

    async def _map_attachment(self, message: Message) -> PlatformAttachment:
        if message.document:
            filename = message.document.file_name or "upload.bin"
            suffix = Path(filename).suffix.lower()
            if suffix in self._binary_extensions:
                buffer = BytesIO()
                await self._bot.download(message.document.file_id, destination=buffer)
                return PlatformAttachment(
                    kind="binary_document",
                    filename=filename,
                    mime_type=message.document.mime_type,
                    binary_content=buffer.getvalue(),
                )

            return PlatformAttachment(
                kind="platform_media",
                filename=filename,
                mime_type=message.document.mime_type,
                platform_file_ref=message.document.file_id,
            )

        if message.video_note:
            return PlatformAttachment(
                kind="platform_media",
                filename="video_note",
                platform_file_ref=message.video_note.file_id,
            )

        if message.video:
            return PlatformAttachment(
                kind="platform_media",
                filename=message.video.file_name or "video.mp4",
                mime_type=message.video.mime_type,
                platform_file_ref=message.video.file_id,
            )

        raise UnsupportedTelegramUpdateError("Unsupported Telegram attachment.")

    @staticmethod
    def _extract_start_payload(text: str | None) -> str | None:
        if not text:
            return None

        command, _, payload = text.partition(" ")
        normalized_command = command.split("@", maxsplit=1)[0]
        if normalized_command != "/start":
            return None

        normalized_payload = payload.strip()
        return normalized_payload or None
