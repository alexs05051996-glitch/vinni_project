"""Простые команды: /help, /me, /unlink, /report (админ)."""

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from bot import config, texts
from bot.repo import telegram_users

router = Router()


@router.message(Command("help"))
async def cmd_help(message: Message) -> None:
    await message.answer(texts.start_help())


@router.message(Command("me"))
async def cmd_me(message: Message) -> None:
    row = telegram_users.get_by_telegram_id(message.from_user.id)
    if row and row.get("user_id"):
        await message.answer(f"✅ Привязан к аккаунту сайта (user_id={row['user_id']}).")
    else:
        await message.answer("Аккаунт ещё не привязан. Получите код в личном кабинете на сайте.")


@router.message(Command("unlink"))
async def cmd_unlink(message: Message) -> None:
    telegram_users.unlink(message.from_user.id)
    await message.answer(texts.unlinked())


@router.message(Command("report"))
async def cmd_report(message: Message) -> None:
    """Ручной запуск отчёта — только для администратора."""
    if message.from_user.id != config.ADMIN_TELEGRAM_ID:
        return
    from bot.scheduler import send_report

    await send_report(message.bot)
