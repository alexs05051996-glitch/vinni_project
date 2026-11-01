"""Команда /start и привязка аккаунта по коду."""

from aiogram import Router
from aiogram.filters import CommandStart
from aiogram.types import Message

from bot import texts
from bot.repo import link_codes, telegram_users

router = Router()


@router.message(CommandStart())
async def cmd_start(message: Message) -> None:
    parts = (message.text or "").split(maxsplit=1)
    payload = parts[1].strip() if len(parts) > 1 else ""

    if not payload:
        await message.answer(texts.start_help())
        return

    user_id = link_codes.consume_code(payload)
    if user_id is None:
        await message.answer(texts.link_invalid())
        return

    telegram_users.link(message.from_user.id, user_id, message.from_user.username)
    await message.answer(texts.link_success())
