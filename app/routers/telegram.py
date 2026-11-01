"""Привязка Telegram-бота к аккаунту сайта."""

from fastapi import APIRouter, Depends, Request

from app.config import BOT_USERNAME
from app.deps import require_user
from app.models import User
from app.templating import render
from bot.repo.link_codes import create_code

router = APIRouter(tags=["telegram"])


@router.get("/dashboard/telegram")
def telegram_page(
    request: Request,
    user: User = Depends(require_user),
):
    """Генерирует код привязки и показывает инструкцию."""
    code = create_code(user.id)
    return render(
        request,
        "telegram.html",
        {"link_code": code, "bot_username": BOT_USERNAME},
    )
