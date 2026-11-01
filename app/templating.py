"""Единая точка настройки Jinja2-шаблонов и хелпер рендеринга."""

from typing import Any, Optional

from fastapi import Request
from fastapi.templating import Jinja2Templates

from app.config import BASE_DIR
from app.flash import pop_flashes

templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))


def render(
    request: Request,
    name: str,
    context: Optional[dict[str, Any]] = None,
    status_code: int = 200,
):
    """Рендерит шаблон, автоматически прокидывая пользователя и flash-сообщения."""
    ctx: dict[str, Any] = {
        "request": request,
        "user": getattr(request.state, "user", None),
        "flashes": pop_flashes(request),
    }
    if context:
        ctx.update(context)
    return templates.TemplateResponse(request, name, ctx, status_code=status_code)
