"""Точка входа Telegram-бота «ВИННИ» (aiogram 3, long polling)."""

import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from bot import config
from bot.db import enable_wal
from bot.handlers import callbacks, commands, start
from bot.middlewares.admin import AdminOnlyMiddleware
from bot.scheduler import setup_scheduler

logging.basicConfig(level=logging.INFO)


def build_dispatcher() -> Dispatcher:
    dp = Dispatcher()
    dp.include_router(start.router)
    dp.include_router(commands.router)
    # Callback-хендлеры (бан) — только для администратора
    callbacks.router.callback_query.middleware(AdminOnlyMiddleware())
    dp.include_router(callbacks.router)
    return dp


async def main() -> None:
    if not config.BOT_TOKEN:
        raise SystemExit("BOT_TOKEN не задан в .env")
    enable_wal()
    bot = Bot(config.BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = build_dispatcher()
    setup_scheduler(bot)
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
