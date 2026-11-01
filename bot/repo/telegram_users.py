"""Связка Telegram ID ↔ пользователь сайта."""

from typing import Optional

from app.models import TelegramUser
from bot.db import session


def get_by_telegram_id(telegram_id: int) -> Optional[dict]:
    with session() as db:
        row = (
            db.query(TelegramUser)
            .filter(TelegramUser.telegram_id == telegram_id)
            .first()
        )
        if row is None:
            return None
        return {
            "telegram_id": row.telegram_id,
            "user_id": row.user_id,
            "tg_username": row.tg_username,
        }


def link(telegram_id: int, user_id: int, tg_username: Optional[str]) -> None:
    """Создаёт/обновляет связку Telegram ID ↔ user_id."""
    with session() as db:
        row = (
            db.query(TelegramUser)
            .filter(TelegramUser.telegram_id == telegram_id)
            .first()
        )
        if row is None:
            row = TelegramUser(telegram_id=telegram_id, tg_username=tg_username)
            db.add(row)
        else:
            row.tg_username = tg_username
        row.user_id = user_id
        db.commit()


def unlink(telegram_id: int) -> None:
    with session() as db:
        row = (
            db.query(TelegramUser)
            .filter(TelegramUser.telegram_id == telegram_id)
            .first()
        )
        if row is not None:
            row.user_id = None
            db.commit()
