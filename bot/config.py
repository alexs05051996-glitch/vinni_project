"""Конфигурация Telegram-бота «ВИННИ».

Читает .env (общий с сайтом) + специфичные для бота переменные.
"""

import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")


def _get_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except (TypeError, ValueError):
        return default


# --- Telegram ---
BOT_TOKEN = os.getenv("BOT_TOKEN", "")
ADMIN_TELEGRAM_ID = _get_int("ADMIN_TELEGRAM_ID", 0)

# --- Отчёты ---
REPORT_INTERVAL_HOURS = _get_int("REPORT_INTERVAL_HOURS", 12)
TOP_TRAFFIC_LIMIT = _get_int("TOP_TRAFFIC_LIMIT", 5)
SUSPICIOUS_IP_THRESHOLD = _get_int("SUSPICIOUS_IP_THRESHOLD", 3)

# --- Ссылки ---
WEB_BASE_URL = os.getenv("WEB_BASE_URL", "https://vinni.fyi").rstrip("/")
