# ВИННИ — Доступ к цифровому сервису

MVP сервиса «Доступа к цифровому сервису» на FastAPI + Jinja2 + SQLite.
Философия **Zero-Config**: клиент ничего не настраивает — всё приезжает в подписке.

## Стек

- Python 3.12, FastAPI, Uvicorn
- Jinja2 + Tailwind CSS (CDN)
- SQLAlchemy (SQLite для MVP, лёгкий переход на PostgreSQL)
- Сессии: `SessionMiddleware` (starlette)
- Пароли: `bcrypt`

## Запуск (локально, через uv)

В этом окружении системный `python` — заглушка Microsoft Store, поэтому используем
менеджер [`uv`](https://docs.astral.sh/uv/).

```powershell
# 1. Создать виртуальное окружение с Python 3.12
uv venv --python 3.12 .venv

# 2. Установить зависимости
uv pip install -r requirements.txt

# 3. Запустить сервер разработки
uv run uvicorn app.main:app --reload
```

Сервер поднимется на http://127.0.0.1:8000

## Учётные данные администратора

Создаётся автоматически при первом запуске:

- **Email:** `admin@vinni.fyi`
- **Пароль:** `admin`

> Смените пароль и `SECRET_KEY` перед публикацией в прод.

## Основные маршруты

| Маршрут | Доступ | Назначение |
|---|---|---|
| `/` | все | лендинг с тарифами и блоком «Скачать» |
| `/register`, `/login`, `/logout` | все | авторизация |
| `/dashboard` | юзер | баланс, пополнение, покупка тарифа, свои подписки |
| `/dashboard/pay` | юзер | заглушка оплаты (ЮKassa / СБП, тестовый режим) |
| `/admin` | админ | генерация ключей и таблица всех ключей |
| `/sub/{uuid}` | все | публичная страница подписки с диплинками |
| `/download/android`, `/download/windows`, `/download/ios` | все | загрузки клиентов |

## Конфигурация

Скопируйте `.env.example` в `.env` и при необходимости отредактируйте:

- `SECRET_KEY` — ключ подписи сессий
- `DATABASE_URL` — строка подключения (для PostgreSQL: `postgresql+psycopg://...`)
- `SUB_BASE_URL` — базовый адрес подписки для диплинков
- `ADMIN_EMAIL`, `ADMIN_PASSWORD` — данные сид-админа

## Структура

```
app/            # код приложения (config, models, routers, deps…)
templates/      # Jinja2-шаблоны (base, страницы, партиалы, макросы)
static/         # статика и файлы загрузок (static/downloads)
```

## Файлы загрузок

- `static/downloads/v2rayNG.apk` — Android (сейчас заглушка, заменить на реальный APK)
- `static/downloads/v2rayN-windows.zip` — Windows-клиент
- iOS — страница-список `/download/ios` с выбором клиента (Streisand, V2Box, FoXray)

## Интеграция с Remnawave

При покупке тарифа создаётся пользователь в панели Remnawave (`POST /api/users`):
передаются `username` (`vinni_{user_id}_{random}`), `expireAt`, `hwidDeviceLimit=3`,
`activeInternalSquads=[squad_uuid]` (по тарифу) и `trafficLimitBytes=0`.

**Транзакционность:** сначала проверяется баланс → затем запрос в панель →
и **только при успехе** списывается баланс и сохраняется `subscriptionUrl`.
Если панель вернула ошибку/таймаут — деньги **не списываются**.

**Mock-режим:** при `REMNAWAVE_ENABLED=false` модуль `app/services/remnawave.py`
не обращается к панели, а возвращает фейковые `uuid` и `subscriptionUrl` —
удобно для локальной разработки.

Переменные окружения (см. `.env.example`):

- `REMNAWAVE_ENABLED`, `REMNAWAVE_BASE_URL`, `REMNAWAVE_API_TOKEN`
- `REMNAWAVE_HWID_LIMIT`, `REMNAWAVE_TRAFFIC_LIMIT_BYTES`, `REMNAWAVE_TIMEOUT`
- `SQUAD_UUID_1M`, `SQUAD_UUID_3M`, `SQUAD_UUID_12M`

## Оплата (заглушка)

`/dashboard/pay` — тестовая страница пополнения (ЮKassa / СБП). Реальная оплата
и вебхуки появятся позже; сейчас сумма зачисляется мгновенно.
