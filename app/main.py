"""Точка входа приложения «ВИННИ» (FastAPI)."""

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from slowapi.errors import RateLimitExceeded
from starlette.middleware.sessions import SessionMiddleware

from app.config import BASE_DIR, SECRET_KEY, SESSION_HTTPS_ONLY
from app.deps import Forbidden, NotAuthenticated
from app.init_db import init_db
from app.ratelimit import (
    TooManyRequests,
    limiter,
    rate_limit_exceeded_handler,
    too_many_requests_handler,
)
from app.routers import admin, auth, downloads, pages, subscriptions, telegram
from app.templating import render


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Создаём таблицы и сид-админа при старте
    init_db()
    yield


app = FastAPI(title="ВИННИ", lifespan=lifespan)

# --- rate limiting (защита от ботов и брутфорса) ---
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, rate_limit_exceeded_handler)
app.add_exception_handler(TooManyRequests, too_many_requests_handler)

app.add_middleware(
    SessionMiddleware,
    secret_key=SECRET_KEY,
    https_only=SESSION_HTTPS_ONLY,
    same_site="lax",
)

app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")


@app.exception_handler(NotAuthenticated)
async def _not_authenticated_handler(request: Request, exc: NotAuthenticated):
    return RedirectResponse(exc.redirect_to, status_code=303)


@app.exception_handler(Forbidden)
async def _forbidden_handler(request: Request, exc: Forbidden):
    return render(request, "403.html", status_code=403)


app.include_router(pages.router)
app.include_router(auth.router)
app.include_router(subscriptions.router)
app.include_router(admin.router)
app.include_router(downloads.router)
app.include_router(telegram.router)
