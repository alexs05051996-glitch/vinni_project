"""Единая точка настройки Jinja2-шаблонов и хелпер рендеринга."""

from typing import Any, Optional

from fastapi import Request
from fastapi.templating import Jinja2Templates

from app.config import (
    BASE_DIR,
    CONTACT_EMAIL,
    ENVIRONMENT,
    IS_PRODUCTION,
    OWNER_INN,
    OWNER_NAME,
)
from app.flash import pop_flashes

templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))

# Доступно во всех шаблонах: {% if IS_PRODUCTION %} ...
templates.env.globals["ENVIRONMENT"] = ENVIRONMENT
templates.env.globals["IS_PRODUCTION"] = IS_PRODUCTION
# Реквизиты владельца / контакты (футер, оферта, политика)
templates.env.globals["owner_name"] = OWNER_NAME
templates.env.globals["owner_inn"] = OWNER_INN
templates.env.globals["contact_email"] = CONTACT_EMAIL


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
