from __future__ import annotations

import logging

from aiogram import F, Router
from aiogram.filters import CommandStart
from aiogram.types import CallbackQuery, Message

from reflebot_telegram_bot.backend.compatibility import MissingPlatformUsernameError
from reflebot_telegram_bot.backend.errors import BackendTransportError, resolve_user_message
from reflebot_telegram_bot.core.planner import ResponsePlanner
from reflebot_telegram_bot.core.use_cases.button import ButtonUseCase
from reflebot_telegram_bot.core.use_cases.file import FileUseCase
from reflebot_telegram_bot.core.use_cases.start import StartUseCase
from reflebot_telegram_bot.core.use_cases.text import TextUseCase
from reflebot_telegram_bot.platforms.telegram.sender import TelegramSender
from reflebot_telegram_bot.platforms.telegram.update_mapper import (
    TelegramUpdateMapper,
    UnsupportedTelegramUpdateError,
)
from reflebot_telegram_bot.settings import Settings

logger = logging.getLogger(__name__)


async def handle_start_message(
    message: Message,
    update_mapper: TelegramUpdateMapper,
    start_use_case: StartUseCase,
    sender: TelegramSender,
    planner: ResponsePlanner,
    settings: Settings,
) -> None:
    try:
        update = await update_mapper.from_start_message(message)
        result = await start_use_case.execute(update)
        await sender.send_batch(result.identity, result.batch)
    except MissingPlatformUsernameError:
        await sender.send_batch(
            update_mapper._identity_from_message(message),
            planner.error_batch(settings.username_required_message),
        )
    except BackendTransportError as exc:
        logger.warning(
            "Backend start/login request failed",
            extra={
                "status_code": exc.status_code,
                "detail": exc.detail,
                "error_code": exc.error_code,
                "has_invite_payload": bool(getattr(update, "start_payload", None)),
            },
        )
        await sender.send_batch(
            update_mapper._identity_from_message(message),
            planner.error_batch(
                resolve_user_message(exc, default_message=settings.user_error_message)
            ),
        )


async def handle_callback_query(
    callback: CallbackQuery,
    update_mapper: TelegramUpdateMapper,
    button_use_case: ButtonUseCase,
    sender: TelegramSender,
    planner: ResponsePlanner,
    settings: Settings,
) -> None:
    update = await update_mapper.from_callback_query(callback)
    await sender.answer_interaction(update.interaction_id)
    try:
        result = await button_use_case.execute(update)
        await sender.send_batch(result.identity, result.batch)
    except BackendTransportError as exc:
        logger.warning(
            "Backend button action failed",
            extra={
                "status_code": exc.status_code,
                "detail": exc.detail,
                "error_code": exc.error_code,
                "has_invite_payload": False,
            },
        )
        await sender.send_batch(
            result_identity_from_update(update),
            planner.error_batch(
                resolve_user_message(exc, default_message=settings.user_error_message)
            ),
        )


async def handle_text_message(
    message: Message,
    update_mapper: TelegramUpdateMapper,
    text_use_case: TextUseCase,
    sender: TelegramSender,
    planner: ResponsePlanner,
    settings: Settings,
) -> None:
    update = await update_mapper.from_text_message(message)
    try:
        result = await text_use_case.execute(update)
        await sender.send_batch(result.identity, result.batch)
    except BackendTransportError as exc:
        logger.warning(
            "Backend text action failed",
            extra={
                "status_code": exc.status_code,
                "detail": exc.detail,
                "error_code": exc.error_code,
                "has_invite_payload": False,
            },
        )
        await sender.send_batch(
            result_identity_from_update(update),
            planner.error_batch(
                resolve_user_message(exc, default_message=settings.user_error_message)
            ),
        )


async def handle_file_message(
    message: Message,
    update_mapper: TelegramUpdateMapper,
    file_use_case: FileUseCase,
    sender: TelegramSender,
    planner: ResponsePlanner,
    settings: Settings,
) -> None:
    identity = update_mapper._identity_from_message(message)
    try:
        update = await update_mapper.from_file_message(message)
        result = await file_use_case.execute(update)
        await sender.send_batch(result.identity, result.batch)
    except UnsupportedTelegramUpdateError:
        await sender.send_batch(identity, planner.error_batch(settings.unsupported_attachment_message))
    except BackendTransportError as exc:
        logger.warning(
            "Backend file action failed",
            extra={
                "status_code": exc.status_code,
                "detail": exc.detail,
                "error_code": exc.error_code,
                "has_invite_payload": False,
            },
        )
        await sender.send_batch(
            identity,
            planner.error_batch(
                resolve_user_message(exc, default_message=settings.user_error_message)
            ),
        )


def build_telegram_router(
    *,
    update_mapper: TelegramUpdateMapper,
    start_use_case: StartUseCase,
    button_use_case: ButtonUseCase,
    text_use_case: TextUseCase,
    file_use_case: FileUseCase,
    sender: TelegramSender,
    planner: ResponsePlanner,
    settings: Settings,
) -> Router:
    router = Router(name="telegram-platform")

    @router.message(CommandStart())
    async def start_handler(message: Message) -> None:
        await handle_start_message(
            message,
            update_mapper,
            start_use_case,
            sender,
            planner,
            settings,
        )

    @router.callback_query()
    async def callback_handler(callback: CallbackQuery) -> None:
        await handle_callback_query(
            callback,
            update_mapper,
            button_use_case,
            sender,
            planner,
            settings,
        )

    @router.message(F.text)
    async def text_handler(message: Message) -> None:
        if not should_forward_text_message(message.text):
            return
        await handle_text_message(
            message,
            update_mapper,
            text_use_case,
            sender,
            planner,
            settings,
        )

    @router.message(F.document | F.video_note | F.video)
    async def file_handler(message: Message) -> None:
        await handle_file_message(
            message,
            update_mapper,
            file_use_case,
            sender,
            planner,
            settings,
        )

    return router


def result_identity_from_update(update) -> object:
    return update.identity


def should_forward_text_message(text: str | None) -> bool:
    if not text:
        return False

    if not text.startswith("/"):
        return True

    command, _, _ = text.partition(" ")
    normalized_command = command.split("@", maxsplit=1)[0]
    return normalized_command == "/join_course"
