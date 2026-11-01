"""Простые flash-сообщения через сессию."""

from typing import Any

from fastapi import Request


def add_flash(request: Request, message: str, category: str = "info") -> None:
    """Добавляет сообщение в очередь (переживёт один редирект)."""
    flashes = request.session.get("flashes", [])
    flashes.append({"message": message, "category": category})
    request.session["flashes"] = flashes


def pop_flashes(request: Request) -> list[dict[str, Any]]:
    """Забирает и очищает очередь сообщений."""
    return request.session.pop("flashes", [])
