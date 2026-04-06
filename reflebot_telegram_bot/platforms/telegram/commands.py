from __future__ import annotations

from aiogram import Bot
from aiogram.types import BotCommand


def build_menu_commands() -> list[BotCommand]:
    return [
        BotCommand(command="start", description="Главное меню"),
        BotCommand(command="join_course", description="Записаться на курс"),
        BotCommand(command="support", description="Тех. поддержка"),
    ]


async def register_menu_commands(bot: Bot) -> None:
    await bot.set_my_commands(build_menu_commands())
