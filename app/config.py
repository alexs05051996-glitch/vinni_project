"""Конфигурация приложения «ВИННИ».

Все значения читаются из переменных окружения (файл .env), с разумными
значениями по умолчанию для локальной разработки.
"""

import os
from pathlib import Path

from dotenv import load_dotenv

# Корень проекта (папка, где лежит app/)
BASE_DIR = Path(__file__).resolve().parent.parent

# Подхватываем .env, если он есть
load_dotenv(BASE_DIR / ".env")


def _get_bool(name: str, default: bool = False) -> bool:
    return os.getenv(name, str(default)).strip().lower() in {"1", "true", "yes", "on"}


def _get_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except (TypeError, ValueError):
        return default


def _get_float(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, str(default)))
    except (TypeError, ValueError):
        return default


# --- Безопасность / сессии ---
SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-change-me")
SESSION_HTTPS_ONLY = _get_bool("SESSION_HTTPS_ONLY", False)

# --- Окружение ---
# "production" отключает тестовые функции (тестовое пополнение и т.п.)
ENVIRONMENT = os.getenv("ENVIRONMENT", "development").strip().lower()
IS_PRODUCTION = ENVIRONMENT == "production"

# --- База данных (легко переключается на PostgreSQL сменой переменной) ---
DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{BASE_DIR / 'vinni.db'}")

# --- Подписка ---
SUB_BASE_URL = os.getenv("SUB_BASE_URL", "https://sub.vinni.fyi").rstrip("/")

# --- Сид-админ (создаётся при первом запуске) ---
ADMIN_EMAIL = os.getenv("ADMIN_EMAIL", "admin@vinni.fyi")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "admin")

# --- Реквизиты владельца / контакты (для футера и правовых страниц) ---
OWNER_NAME = os.getenv("OWNER_NAME", "[Ваше ФИО]")
OWNER_INN = os.getenv("OWNER_INN", "[Ваш ИНН]")
CONTACT_EMAIL = os.getenv("CONTACT_EMAIL", "support@vinni.fyi")

# --- ЮKassa (приём платежей: СБП, QR, карты) ---
# YOOKASSA_ENABLED=true + заполненные ключи => реальные платежи.
# Без ключей клиент работает в mock-режиме (для тестов).
YOOKASSA_ENABLED = _get_bool("YOOKASSA_ENABLED", False)
YOOKASSA_SHOP_ID = os.getenv("YOOKASSA_SHOP_ID", "")
YOOKASSA_SECRET_KEY = os.getenv("YOOKASSA_SECRET_KEY", "")
YOOKASSA_RETURN_URL = os.getenv("YOOKASSA_RETURN_URL", "https://vinni.fyi/dashboard")
YOOKASSA_API_URL = os.getenv("YOOKASSA_API_URL", "https://api.yookassa.ru/v3")

# --- Интеграция с панелью Remnawave ---
# REMNAWAVE_ENABLED=false включает mock-режим (без обращения к панели)
REMNAWAVE_ENABLED = _get_bool("REMNAWAVE_ENABLED", False)
REMNAWAVE_BASE_URL = os.getenv("REMNAWAVE_BASE_URL", "https://panel.vinni.fyi:8443").rstrip("/")
REMNAWAVE_API_TOKEN = os.getenv("REMNAWAVE_API_TOKEN", "")
REMNAWAVE_HWID_LIMIT = _get_int("REMNAWAVE_HWID_LIMIT", 3)
REMNAWAVE_TRAFFIC_LIMIT_BYTES = _get_int("REMNAWAVE_TRAFFIC_LIMIT_BYTES", 0)
REMNAWAVE_TIMEOUT = _get_float("REMNAWAVE_TIMEOUT", 15.0)

# --- Пробный период (trial) ---
TRIAL_SQUAD_UUID = os.getenv("SQUAD_UUID_TRIAL", "")
TRIAL_DAYS = _get_int("TRIAL_DAYS", 3)
# 10 ГБ = 10737418240 байт
TRIAL_TRAFFIC_LIMIT_BYTES = _get_int("TRIAL_TRAFFIC_LIMIT_BYTES", 10737418240)

# --- iOS-клиенты (App Store) ---
# deeplink — шаблон со {url}; если None, на странице подписки показываем
# кнопку «Скопировать ссылку».
IOS_CLIENTS: list[dict] = [
    {
        "key": "streisand",
        "name": "Streisand",
        "subtitle": "Flexible Proxy Client",
        "url": "https://apps.apple.com/us/app/streisand/id6450534064",
        "deeplink": "streisand://import/{url}",
    },
    {
        "key": "v2box",
        "name": "V2Box",
        "subtitle": "V2ray Client",
        "url": "https://apps.apple.com/us/app/v2box-v2ray-client/id6446814690",
        "deeplink": "v2box://install-sub?url={url}",
    },
    {
        "key": "foxray",
        "name": "FoXray",
        "subtitle": "V2ray / Xray Client",
        # TODO: заменить на прямую ссылку приложения (карточка в US App Store недоступна).
        # Пока ведём на поиск в App Store; схема деплинка неизвестна — на странице
        # подписки будет кнопка «Скопировать ссылку».
        "url": "https://apps.apple.com/us/search?term=foxray",
        "deeplink": None,
    },
]

# --- Тарифы для обычных пользователей ---
# price — цена в рублях, days — срок действия, squad_uuid — группа в Remnawave
PLANS: dict[str, dict] = {
    "1_month": {
        "name": "1 месяц",
        "price": 200.0,
        "days": 30,
        "squad_uuid": os.getenv("SQUAD_UUID_1M", ""),
    },
    "3_month": {
        "name": "3 месяца",
        "price": 500.0,
        "days": 90,
        "squad_uuid": os.getenv("SQUAD_UUID_3M", ""),
    },
    "12_month": {
        "name": "12 месяцев",
        "price": 1800.0,
        "days": 365,
        "squad_uuid": os.getenv("SQUAD_UUID_12M", ""),
    },
}

# Сумма быстрого тестового пополнения баланса
TOPUP_AMOUNT = 500.0

# Пресеты сумм на странице оплаты (заглушка ЮKassa/СБП)
PAYMENT_AMOUNTS = [500, 1000, 2000, 5000]
