"""Middleware: пропускает только администратора."""

from typing import Any

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject

from bot import config


class AdminOnlyMiddleware(BaseMiddleware):
    """Пускает дальше только telegram_id == ADMIN_TELEGRAM_ID."""

    async def __call__(self, handler, event: TelegramObject, data: dict[str, Any]):
        user = data.get("event_from_user")
        if user is None or config.ADMIN_TELEGRAM_ID == 0:
            return None
        if user.id != config.ADMIN_TELEGRAM_ID:
            return None
        return await handler(event, data)
