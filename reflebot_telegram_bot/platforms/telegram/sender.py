from __future__ import annotations

from datetime import UTC, datetime

from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from reflebot_telegram_bot.core.models import (
    PlatformButton,
    PlatformDeliveryResult,
    PlatformIdentity,
    PlatformMedia,
    PlatformMessage,
    PlatformMessageBatch,
)
from reflebot_telegram_bot.core.ports import PlatformCapabilities, PlatformSender


class TelegramSender(PlatformSender):
    def __init__(self, bot: Bot) -> None:
        self._bot = bot
        self._capabilities = PlatformCapabilities(
            supports_message_edit=True,
            supports_inline_buttons=True,
            supports_platform_media_refs=True,
            supports_video_note=True,
        )

    @property
    def platform_name(self) -> str:
        return "telegram"

    @property
    def capabilities(self) -> PlatformCapabilities:
        return self._capabilities

    async def send_batch(
        self,
        identity: PlatformIdentity,
        batch: PlatformMessageBatch,
    ) -> PlatformDeliveryResult:
        primary_message_id = await self._send_primary_message(identity, batch.primary_message)

        for media in batch.primary_message.media:
            await self._send_media(identity, media)

        for follow_up in batch.follow_up_messages:
            if follow_up.text:
                await self._bot.send_message(
                    chat_id=int(identity.chat_id),
                    text=follow_up.text,
                    parse_mode=follow_up.parse_mode,
                    reply_markup=self._build_keyboard(follow_up.buttons),
                )
            for media in follow_up.media:
                await self._send_media(identity, media)

        return PlatformDeliveryResult(
            primary_message_id=str(primary_message_id) if primary_message_id is not None else None,
            sent_at=datetime.now(UTC),
        )

    async def answer_interaction(self, interaction_id: str | None) -> None:
        if interaction_id is None:
            return
        await self._bot.answer_callback_query(callback_query_id=interaction_id)

    async def download_binary_attachment(self, file_ref: str) -> bytes:
        from io import BytesIO

        buffer = BytesIO()
        await self._bot.download(file_ref, destination=buffer)
        return buffer.getvalue()

    async def _send_primary_message(
        self,
        identity: PlatformIdentity,
        message: PlatformMessage,
    ) -> int | None:
        keyboard = self._build_keyboard(message.buttons)
        if message.edit_target_message_id is not None:
            try:
                edited = await self._bot.edit_message_text(
                    chat_id=int(identity.chat_id),
                    message_id=int(message.edit_target_message_id),
                    text=message.text or "",
                    parse_mode=message.parse_mode,
                    reply_markup=keyboard,
                )
                return getattr(edited, "message_id", int(message.edit_target_message_id))
            except TelegramBadRequest:
                pass

        sent = await self._bot.send_message(
            chat_id=int(identity.chat_id),
            text=message.text or "",
            parse_mode=message.parse_mode,
            reply_markup=keyboard,
        )
        return getattr(sent, "message_id", None)

    async def _send_media(self, identity: PlatformIdentity, media: PlatformMedia) -> None:
        file_ref = media.platform_file_ref
        if file_ref is None:
            return

        kind = media.kind.lower()
        chat_id = int(identity.chat_id)
        if kind == "presentation":
            await self._bot.send_document(chat_id=chat_id, document=file_ref)
            return
        if kind == "recording":
            await self._bot.send_video(chat_id=chat_id, video=file_ref)
            return
        if kind == "qa_video":
            try:
                await self._bot.send_video_note(chat_id=chat_id, video_note=file_ref)
                return
            except TelegramBadRequest:
                await self._bot.send_video(chat_id=chat_id, video=file_ref)
                return
        await self._bot.send_document(chat_id=chat_id, document=file_ref)

    @staticmethod
    def _build_keyboard(buttons: list[PlatformButton]) -> InlineKeyboardMarkup | None:
        if not buttons:
            return None
        return InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text=button.text, callback_data=button.action)]
                for button in buttons
            ]
        )
