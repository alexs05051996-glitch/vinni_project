"""Коды привязки Telegram ↔ аккаунт сайта."""

import secrets
from datetime import datetime, timedelta
from typing import Optional

from app.models import TelegramLinkCode
from bot.db import session

CODE_TTL_MINUTES = 15


def create_code(user_id: int) -> str:
    """Создаёт одноразовый код привязки для пользователя сайта."""
    code = secrets.token_hex(3).upper()  # 6 символов
    with session() as db:
        db.add(
            TelegramLinkCode(
                code=code,
                user_id=user_id,
                expires_at=datetime.utcnow() + timedelta(minutes=CODE_TTL_MINUTES),
            )
        )
        db.commit()
    return code


def consume_code(code: str) -> Optional[int]:
    """Проверяет код, помечает использованным и возвращает user_id (или None)."""
    code = (code or "").strip().upper()
    if not code:
        return None
    with session() as db:
        row = (
            db.query(TelegramLinkCode)
            .filter(TelegramLinkCode.code == code)
            .first()
        )
        if row is None or row.used_at is not None or row.expires_at < datetime.utcnow():
            return None
        row.used_at = datetime.utcnow()
        db.commit()
        return row.user_id
