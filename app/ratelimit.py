"""Ограничение частоты запросов (rate limiting) — защита от ботов и брутфорса.

Ключ — реальный IP клиента. В прод запросы приходят через Caddy (reverse proxy),
который **дописывает** IP клиента в конец ``X-Forwarded-For``, поэтому берём
последний элемент списка: всё, что левее, может быть подделано клиентом.

Лимиты настраиваются переменными окружения (формат ``limits``: "5/minute",
"30/hour" и т.п.), значения по умолчанию — жёсткие.
"""

import logging
import os

from limits import parse as parse_limit
from limits.storage import MemoryStorage
from limits.strategies import MovingWindowRateLimiter
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address
from starlette.requests import Request
from starlette.responses import HTMLResponse, JSONResponse, Response

logger = logging.getLogger("vinni.ratelimit")


def client_ip(request: Request) -> str:
    """Реальный IP клиента (последний элемент X-Forwarded-For, иначе peer)."""
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        parts = [part.strip() for part in forwarded.split(",") if part.strip()]
        if parts:
            return parts[-1]
    return get_remote_address(request)


limiter = Limiter(key_func=client_ip, headers_enabled=False, default_limits=[])

# --- лимиты (переопределяются через окружение) ---
# вход: 5 попыток в минуту и 30 в час с одного IP
LOGIN_LIMIT = os.getenv("RATE_LIMIT_LOGIN", "5/minute")
LOGIN_LIMIT_LONG = os.getenv("RATE_LIMIT_LOGIN_LONG", "30/hour")
# регистрация: не более 5 аккаунтов в минуту и 20 в час с одного IP
REGISTER_LIMIT = os.getenv("RATE_LIMIT_REGISTER", "5/minute")
REGISTER_LIMIT_LONG = os.getenv("RATE_LIMIT_REGISTER_LONG", "20/hour")
# пробный период: 5 попыток в минуту
TRIAL_LIMIT = os.getenv("RATE_LIMIT_TRIAL", "5/minute")

_RATE_LIMIT_HTML = """<!doctype html>
<html lang="ru">
  <head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Слишком много запросов</title>
    <style>
      body {{ font-family: system-ui, sans-serif; margin: 0; min-height: 100vh;
             display: grid; place-items: center; background: #0f172a; color: #e2e8f0; }}
      main {{ text-align: center; padding: 2rem; max-width: 32rem; }}
      h1 {{ font-size: 1.5rem; }}
      p {{ color: #94a3b8; }}
    </style>
  </head>
  <body>
    <main>
      <h1>429 — слишком много запросов</h1>
      <p>Слишком много попыток с вашего IP. Повторите через {retry_after} сек.</p>
    </main>
  </body>
</html>
"""


def rate_limit_exceeded_handler(request: Request, exc: RateLimitExceeded) -> Response:
    """Ответ 429 для лимитов slowapi (декораторы)."""
    retry_after = 60
    try:
        retry_after = max(1, int(exc.limit.limit.get_expiry()))
    except Exception:  # noqa: BLE001 — не критично, отдаём значение по умолчанию
        pass

    logger.warning(
        "rate limit exceeded: ip=%s path=%s limit=%s",
        client_ip(request),
        request.url.path,
        getattr(exc, "detail", "?"),
    )
    return _build_429(request, retry_after)


# --- лимит до аутентификации (FastAPI-зависимость) --------------------------
class TooManyRequests(Exception):
    """429, выбрасываемый до выполнения эндпоинта (в т.ч. до проверки авторизации)."""

    def __init__(self, retry_after: int):
        self.retry_after = retry_after


_trial_storage = MemoryStorage()
_trial_window = MovingWindowRateLimiter(_trial_storage)
_trial_rule = parse_limit(TRIAL_LIMIT)


def trial_guard(request: Request) -> None:
    """Лимит на /dashboard/trial ещё до аутентификации (анонимный флуд тоже режется)."""
    if not _trial_window.hit(_trial_rule, client_ip(request), "dashboard-trial"):
        logger.warning(
            "rate limit exceeded: ip=%s path=%s limit=%s",
            client_ip(request),
            request.url.path,
            TRIAL_LIMIT,
        )
        raise TooManyRequests(retry_after=max(1, int(_trial_rule.get_expiry())))


def too_many_requests_handler(request: Request, exc: TooManyRequests) -> Response:
    """Ответ 429 для лимита-зависимости."""
    return _build_429(request, exc.retry_after)


def _build_429(request: Request, retry_after: int) -> Response:
    """Формирует ответ 429: HTML для браузера, JSON для API-клиентов."""
    headers = {"Retry-After": str(retry_after)}
    accept = request.headers.get("accept", "")
    if "text/html" in accept:
        return HTMLResponse(
            _RATE_LIMIT_HTML.format(retry_after=retry_after),
            status_code=429,
            headers=headers,
        )
    return JSONResponse(
        {"detail": "Too Many Requests", "retry_after": retry_after},
        status_code=429,
        headers=headers,
    )
