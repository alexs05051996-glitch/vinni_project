"""Зависимости FastAPI: получение текущего пользователя и защита роутов."""

from typing import Optional

from fastapi import Depends, Request
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User


class NotAuthenticated(Exception):
    """Пользователь не авторизован — переадресуем на страницу входа."""

    def __init__(self, redirect_to: str = "/login"):
        self.redirect_to = redirect_to


class Forbidden(Exception):
    """Пользователь авторизован, но не имеет прав доступа."""

    def __init__(self, detail: str = "Доступ запрещён"):
        self.detail = detail


def get_optional_user(
    request: Request,
    db: Session = Depends(get_db),
) -> Optional[User]:
    """Возвращает текущего пользователя или None.

    Дополнительно кладёт пользователя в request.state.user, чтобы шаблоны
    могли обращаться к нему как ``request.state.user``.
    """
    user: Optional[User] = None
    user_id = request.session.get("user_id")
    if user_id is not None:
        user = db.get(User, user_id)
        if user is None:
            # Сессия ссылается на несуществующего пользователя — чистим её
            request.session.clear()
    request.state.user = user
    return user


def require_user(user: Optional[User] = Depends(get_optional_user)) -> User:
    """Гарантирует, что пользователь авторизован."""
    if user is None:
        raise NotAuthenticated("/login")
    return user


def require_admin(user: Optional[User] = Depends(get_optional_user)) -> User:
    """Гарантирует, что пользователь авторизован и имеет роль admin."""
    if user is None:
        raise NotAuthenticated("/login")
    if user.role != "admin":
        raise Forbidden("Доступ только для администратора")
    return user
