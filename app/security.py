"""Хеширование паролей и генерация ключей подписки."""

import uuid as _uuid

import bcrypt


def hash_password(password: str) -> str:
    """Возвращает bcrypt-хеш пароля в виде строки."""
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    """Проверяет пароль против хеша. Не бросает исключений при мусорном хеше."""
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
    except (ValueError, TypeError):
        return False


def new_uuid() -> str:
    """Генерирует уникальный идентификатор подписки."""
    return str(_uuid.uuid4())
