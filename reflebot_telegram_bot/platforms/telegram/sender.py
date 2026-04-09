from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
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
from reflebot_telegram_bot.platforms.telegram.rate_limiter import SlidingWindowRateLimiter

logger = logging.getLogger(__name__)


class TelegramSender(PlatformSender):
    def __init__(
        self,
        bot: Bot,
        *,
        rate_limiter: SlidingWindowRateLimiter | None = None,
    ) -> None:
        self._bot = bot
        self._rate_limiter = rate_limiter or SlidingWindowRateLimiter(20)
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
                await self._throttled_request(
                    self._bot.send_message,
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

    async def edit_batch(
        self,
        identity: PlatformIdentity,
        batch: PlatformMessageBatch,
    ) -> PlatformDeliveryResult:
        primary_message_id = await self._edit_primary_message_strict(
            identity,
            batch.primary_message,
        )
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
                edited = await self._throttled_request(
                    self._bot.edit_message_text,
                    chat_id=int(identity.chat_id),
                    message_id=int(message.edit_target_message_id),
                    text=message.text or "",
                    parse_mode=message.parse_mode,
                    reply_markup=keyboard,
                )
                return getattr(edited, "message_id", int(message.edit_target_message_id))
            except TelegramBadRequest:
                pass

        sent = await self._throttled_request(
            self._bot.send_message,
            chat_id=int(identity.chat_id),
            text=message.text or "",
            parse_mode=message.parse_mode,
            reply_markup=keyboard,
        )
        return getattr(sent, "message_id", None)

    async def _edit_primary_message_strict(
        self,
        identity: PlatformIdentity,
        message: PlatformMessage,
    ) -> int | None:
        if message.edit_target_message_id is None:
            raise ValueError("edit_target_message_id is required for strict message edit.")

        try:
            edited = await self._throttled_request(
                self._bot.edit_message_text,
                chat_id=int(identity.chat_id),
                message_id=int(message.edit_target_message_id),
                text=message.text or "",
                parse_mode=message.parse_mode,
                reply_markup=self._build_keyboard(message.buttons),
            )
        except TelegramBadRequest as exc:
            if "message is not modified" in str(exc).lower():
                logger.info(
                    (
                        "Telegram message edit skipped because message is not modified "
                        "chat_id=%s message_id=%s buttons_count=%s text_length=%s"
                    ),
                    identity.chat_id,
                    message.edit_target_message_id,
                    len(message.buttons),
                    len(message.text or ""),
                )
                return int(message.edit_target_message_id)
            raise
        logger.info(
            (
                "Telegram message edited successfully chat_id=%s "
                "message_id=%s buttons_count=%s text_length=%s"
            ),
            identity.chat_id,
            message.edit_target_message_id,
            len(message.buttons),
            len(message.text or ""),
        )
        return getattr(edited, "message_id", int(message.edit_target_message_id))

    async def _send_media(self, identity: PlatformIdentity, media: PlatformMedia) -> None:
        file_ref = media.platform_file_ref
        if file_ref is None:
            return

        kind = media.kind.lower()
        chat_id = int(identity.chat_id)
        if kind == "presentation":
            await self._throttled_request(self._bot.send_document, chat_id=chat_id, document=file_ref)
            return
        if kind == "recording":
            await self._throttled_request(self._bot.send_video, chat_id=chat_id, video=file_ref)
            return
        if kind == "qa_video":
            try:
                await self._throttled_request(
                    self._bot.send_video_note,
                    chat_id=chat_id,
                    video_note=file_ref,
                )
                return
            except TelegramBadRequest:
                await self._throttled_request(self._bot.send_video, chat_id=chat_id, video=file_ref)
                return
        await self._throttled_request(self._bot.send_document, chat_id=chat_id, document=file_ref)

    async def _throttled_request(
        self,
        method: Callable[..., Awaitable[object]],
        /,
        **kwargs,
    ) -> object:
        await self._rate_limiter.acquire()
        return await method(**kwargs)

    @staticmethod
    def _build_keyboard(buttons: list[PlatformButton]) -> InlineKeyboardMarkup | None:
        if not buttons:
            return None
        inline_keyboard: list[list[InlineKeyboardButton]] = []
        for button in buttons:
            if button.url:
                inline_keyboard.append([InlineKeyboardButton(text=button.text, url=button.url)])
                continue
            if button.action:
                inline_keyboard.append(
                    [InlineKeyboardButton(text=button.text, callback_data=button.action)]
                )
        if not inline_keyboard:
            return None
        return InlineKeyboardMarkup(
            inline_keyboard=inline_keyboard
        )
