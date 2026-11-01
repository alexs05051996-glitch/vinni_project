"""Покупка тарифов, пополнение баланса, оплата (заглушка) и страница подписки."""

import logging
import secrets
from datetime import datetime, timedelta

from fastapi import APIRouter, BackgroundTasks, Depends, Form, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.config import (
    IOS_CLIENTS,
    IS_PRODUCTION,
    PAYMENT_AMOUNTS,
    PLANS,
    REMNAWAVE_HWID_LIMIT,
    REMNAWAVE_TRAFFIC_LIMIT_BYTES,
    SUB_BASE_URL,
    TOPUP_AMOUNT,
    TRIAL_DAYS,
    TRIAL_SQUAD_UUID,
    TRIAL_TRAFFIC_LIMIT_BYTES,
    YOOKASSA_ENABLED,
)
from app.database import get_db
from app.deps import get_optional_user, require_user
from app.flash import add_flash
from app.models import Subscription, User
from app.security import new_uuid
from app.ratelimit import trial_guard
from app.services.remnawave import RemnawaveError, get_client
from app.services.yookassa import YooKassaError, get_yookassa_client
from app.templating import render

logger = logging.getLogger("vinni.subscriptions")

router = APIRouter(tags=["subscriptions"])

PAYMENT_METHOD_LABELS = {"sbp": "СБП", "yookassa": "ЮKassa"}


ANDROID_STEPS = [
    "Разрешите установку из неизвестных источников.",
    "Установите v2rayNG.",
    "Откройте приложение и разрешите создание VPN-подключения.",
    "Скопируйте ссылку на подписку выше.",
    "В приложении нажмите «+» (плюсик) в правом верхнем углу → «Импорт из буфера обмена».",
    "Выберите появившееся подключение и нажмите круглую кнопку Play (она станет жёлтой). "
    "Внизу появится ваш IP и пинг.",
]

IOS_STEPS = [
    "Установите одно из приложений из App Store: Streisand, V2Box или FoXray.",
    "Скопируйте ссылку на подписку выше.",
    "Откройте приложение и добавьте подписку из буфера обмена.",
    "(Текст инструкции для iOS будет уточнён позже.)",
]

WINDOWS_STEPS = [
    "Скачайте и распакуйте архив v2rayN.",
    "Запустите v2rayN.exe.",
    "Скопируйте ссылку на подписку выше.",
    "В v2rayN откройте «Подписки» → «Добавить подписку из буфера обмена».",
    "(Текст инструкции для Windows будет уточнён позже.)",
]


def _build_platforms() -> list[dict]:
    """Данные для вкладок: список приложений для скачивания + пошаговые инструкции."""
    return [
        {
            "key": "android",
            "label": "Android",
            "img_id": "instruction-img-android",
            "steps": ANDROID_STEPS,
            "apps": [
                {
                    "name": "v2rayNG",
                    "subtitle": "Приложение для Android",
                    "url": "/download/android",
                    "button": "Скачать APK",
                    "external": False,
                }
            ],
        },
        {
            "key": "ios",
            "label": "iOS",
            "img_id": "instruction-img-ios",
            "steps": IOS_STEPS,
            "apps": [
                {
                    "name": client["name"],
                    "subtitle": client["subtitle"],
                    "url": client["url"],
                    "button": "В App Store",
                    "external": True,
                }
                for client in IOS_CLIENTS
            ],
        },
        {
            "key": "windows",
            "label": "Windows",
            "img_id": "instruction-img-windows",
            "steps": WINDOWS_STEPS,
            "apps": [
                {
                    "name": "v2rayN",
                    "subtitle": "Клиент для Windows",
                    "url": "/download/windows",
                    "button": "Скачать архив",
                    "external": False,
                }
            ],
        },
    ]


def _yookassa_active() -> bool:
    """Оплата через ЮKassa включается в проде при YOOKASSA_ENABLED=true."""
    return IS_PRODUCTION and YOOKASSA_ENABLED


def _send_mock_webhook(base_url: str, payment_id: str, plan_id: str, user_id: int) -> None:
    """Mock-режим: эндпоинт «шлёт вебхук сам себе» (после ответа)."""
    import httpx

    try:
        httpx.post(
            f"{base_url}/webhook/yookassa",
            json={
                "event": "payment.succeeded",
                "object": {
                    "id": payment_id,
                    "status": "succeeded",
                    "metadata": {"plan_id": str(plan_id), "user_id": str(user_id)},
                },
            },
            timeout=10.0,
        )
    except Exception:  # noqa: BLE001
        logger.exception("Mock-вебхук ЮKassa: не удалось отправить уведомление")


def _start_yookassa_payment(
    request: Request,
    background_tasks: BackgroundTasks,
    plan_key: str,
    user: User,
    use_sbp: bool = False,
):
    """Создаёт платёж в ЮKassa и редиректит пользователя на страницу оплаты."""
    selected = PLANS.get(plan_key)
    if selected is None:
        add_flash(request, "Неизвестный тариф.", "error")
        return RedirectResponse("/dashboard", status_code=303)

    client = get_yookassa_client()
    try:
        payment = client.create_payment(
            amount=selected["price"],
            plan_id=plan_key,
            user_id=user.id,
            description=f"Подписка «{selected['name']}»",
            use_sbp=use_sbp,
        )
    except YooKassaError as exc:
        logger.warning("Не удалось создать платёж ЮKassa: %s", exc)
        add_flash(request, "Не удалось создать платёж. Попробуйте позже.", "error")
        return RedirectResponse("/dashboard", status_code=303)

    if not payment.confirmation_url:
        add_flash(request, "ЮKassa не вернула ссылку на оплату.", "error")
        return RedirectResponse("/dashboard", status_code=303)

    # В mock-режиме вебхук отправляем сами себе
    if client.is_mock:
        base_url = str(request.base_url).rstrip("/")
        background_tasks.add_task(
            _send_mock_webhook, base_url, payment.payment_id, plan_key, user.id
        )

    return RedirectResponse(payment.confirmation_url, status_code=303)


@router.post("/dashboard/topup")
def topup(
    request: Request,
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
):
    # Тестовое пополнение отключено в продакшене
    if IS_PRODUCTION:
        raise HTTPException(status_code=404, detail="Not Found")

    user.balance = (user.balance or 0.0) + TOPUP_AMOUNT
    db.add(user)
    db.commit()
    add_flash(request, f"Баланс пополнен на {TOPUP_AMOUNT:.0f} ₽ (тест)", "success")
    return RedirectResponse("/dashboard", status_code=303)


@router.get("/dashboard/pay")
def pay_page(
    request: Request,
    user: User = Depends(require_user),
):
    # Заглушка оплаты (ЮKassa / СБП) — реальная интеграция позже
    return render(request, "payment.html", {"amounts": PAYMENT_AMOUNTS})


@router.post("/dashboard/pay/confirm")
def pay_confirm(
    request: Request,
    amount: float = Form(...),
    method: str = Form("sbp"),
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
):
    # Тестовое подтверждение оплаты отключено в продакшене
    if IS_PRODUCTION:
        raise HTTPException(status_code=404, detail="Not Found")

    if amount is None or amount <= 0:
        add_flash(request, "Укажите корректную сумму пополнения.", "error")
        return RedirectResponse("/dashboard/pay", status_code=303)

    user.balance = (user.balance or 0.0) + amount
    db.add(user)
    db.commit()

    label = PAYMENT_METHOD_LABELS.get(method, method)
    add_flash(request, f"Платёж ({label}, тест) на {amount:.0f} ₽ зачислен на баланс.", "success")
    return RedirectResponse("/dashboard", status_code=303)


@router.post("/dashboard/pay/sbp")
def pay_sbp(
    request: Request,
    background_tasks: BackgroundTasks,
    plan: str = Form(...),
    user: User = Depends(require_user),
):
    """Оплата тарифа через СБП (QR-код) — реальные деньги через ЮKassa."""
    if not _yookassa_active():
        raise HTTPException(status_code=404, detail="Not Found")
    return _start_yookassa_payment(request, background_tasks, plan, user, use_sbp=True)


@router.post("/dashboard/buy")
def buy(
    request: Request,
    background_tasks: BackgroundTasks,
    plan: str = Form(...),
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
):
    selected = PLANS.get(plan)
    if selected is None:
        add_flash(request, "Неизвестный тариф.", "error")
        return RedirectResponse("/dashboard", status_code=303)

    # В проде с включённой ЮKassa — оплата реальными деньгами (баланс НЕ списываем)
    if _yookassa_active():
        return _start_yookassa_payment(request, background_tasks, plan, user, use_sbp=False)

    # 1) Проверяем баланс (деньги ещё НЕ списываем)
    if (user.balance or 0.0) < selected["price"]:
        add_flash(request, "Недостаточно средств на балансе.", "error")
        return RedirectResponse("/dashboard", status_code=303)

    expires_at = datetime.utcnow() + timedelta(days=selected["days"])
    username = f"vinni_{user.id}_{secrets.token_hex(3)}"
    squad_uuid = selected.get("squad_uuid")
    squad_uuids = [squad_uuid] if squad_uuid else None

    # 2) Сначала создаём пользователя в панели Remnawave
    try:
        remna_user = get_client().create_user(
            username=username,
            expire_at=expires_at,
            squad_uuids=squad_uuids,
            hwid_device_limit=REMNAWAVE_HWID_LIMIT,
            traffic_limit_bytes=REMNAWAVE_TRAFFIC_LIMIT_BYTES,
            email=user.email,
        )
    except RemnawaveError as exc:
        logger.warning("Не удалось создать пользователя в Remnawave: %s", exc)
        add_flash(
            request,
            "Не удалось создать подписку. Деньги не списаны, попробуйте позже.",
            "error",
        )
        return RedirectResponse("/dashboard", status_code=303)

    # 3) Успех — только теперь списываем баланс и сохраняем подписку
    user.balance = (user.balance or 0.0) - selected["price"]
    subscription = Subscription(
        user_id=user.id,
        uuid=new_uuid(),
        plan_name=selected["name"],
        owner_name=user.email,
        is_active=True,
        expires_at=expires_at,
        remnawave_uuid=remna_user.uuid,
        subscription_url=remna_user.subscription_url,
    )
    try:
        db.add(subscription)
        db.add(user)
        db.commit()
    except Exception:
        db.rollback()
        logger.exception(
            "Сбой записи в БД после создания пользователя в Remnawave (uuid=%s). "
            "Требуется компенсирующее действие (disable/delete).",
            remna_user.uuid,
        )
        add_flash(request, "Ошибка сохранения подписки. Обратитесь в поддержку.", "error")
        return RedirectResponse("/dashboard", status_code=303)

    add_flash(request, f"Тариф «{selected['name']}» активирован! Подключитесь в кабинете.", "success")
    return RedirectResponse("/dashboard", status_code=303)


@router.post("/dashboard/trial", dependencies=[Depends(trial_guard)])
def trial(
    request: Request,
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
):
    """Пробный доступ на 3 дня / 10 ГБ (один раз на аккаунт)."""
    if user.has_used_trial:
        add_flash(request, "Пробный период уже использован.", "error")
        return RedirectResponse("/dashboard", status_code=303)

    expires_at = datetime.utcnow() + timedelta(days=TRIAL_DAYS)
    username = f"vinni_{user.id}_trial_{secrets.token_hex(3)}"
    squad_uuids = [TRIAL_SQUAD_UUID] if TRIAL_SQUAD_UUID else None

    # 1) Сначала создаём пользователя в панели (до отметки об использовании)
    try:
        remna_user = get_client().create_user(
            username=username,
            expire_at=expires_at,
            squad_uuids=squad_uuids,
            hwid_device_limit=REMNAWAVE_HWID_LIMIT,
            traffic_limit_bytes=TRIAL_TRAFFIC_LIMIT_BYTES,
            email=user.email,
        )
    except RemnawaveError as exc:
        logger.warning("Не удалось создать пробную подписку в Remnawave: %s", exc)
        add_flash(request, "Не удалось активировать пробный период. Попробуйте позже.", "error")
        return RedirectResponse("/dashboard", status_code=303)

    # 2) Успех — сохраняем подписку и ставим флаг has_used_trial
    subscription = Subscription(
        user_id=user.id,
        uuid=new_uuid(),
        plan_name=f"Пробный период ({TRIAL_DAYS} дня)",
        owner_name=user.email,
        is_active=True,
        expires_at=expires_at,
        remnawave_uuid=remna_user.uuid,
        subscription_url=remna_user.subscription_url,
    )
    user.has_used_trial = True
    try:
        db.add(subscription)
        db.add(user)
        db.commit()
    except Exception:
        db.rollback()
        logger.exception(
            "Сбой записи пробной подписки в БД (remnawave uuid=%s).",
            remna_user.uuid,
        )
        add_flash(request, "Ошибка сохранения пробной подписки. Обратитесь в поддержку.", "error")
        return RedirectResponse("/dashboard", status_code=303)

    add_flash(request, f"Пробный период на {TRIAL_DAYS} дня активирован! Подключитесь в кабинете.", "success")
    return RedirectResponse("/dashboard", status_code=303)


@router.get("/sub/{uuid}")
def subscription_page(
    request: Request,
    uuid: str,
    db: Session = Depends(get_db),
    user: User | None = Depends(get_optional_user),
):
    subscription = db.query(Subscription).filter(Subscription.uuid == uuid).first()
    if subscription is None:
        return render(request, "404.html", status_code=404)

    # Реальная ссылка из панели Remnawave, либо запасной вариант по нашему uuid
    sub_url = subscription.subscription_url or f"{SUB_BASE_URL}/{subscription.uuid}"
    return render(
        request,
        "subscription.html",
        {
            "subscription": subscription,
            "sub_url": sub_url,
            "platforms": _build_platforms(),
        },
    )


@router.post("/webhook/yookassa")
async def yookassa_webhook(
    request: Request,
    db: Session = Depends(get_db),
):
    """Уведомление от ЮKassa об оплате.

    ЮKassa вызывает этот адрес при изменении статуса платежа. Мы:
    1) проверяем статус платежа в API ЮKassa,
    2) создаём пользователя в панели Remnawave,
    3) сохраняем подписку в БД.
    Повторные уведомления по одному платежу игнорируются (по payment_id).
    """
    try:
        body = await request.json()
    except Exception:  # noqa: BLE001
        raise HTTPException(status_code=400, detail="Bad request")

    obj = body.get("object") or {}
    payment_id = obj.get("id")
    if not payment_id:
        raise HTTPException(status_code=400, detail="No payment id")

    # 1) Проверяем платёж в API ЮKassa (защита от подделки вебхука)
    client = get_yookassa_client()
    try:
        payment = client.get_payment(payment_id)
    except YooKassaError as exc:
        logger.warning("Вебхук ЮKassa: не удалось проверить платёж %s: %s", payment_id, exc)
        raise HTTPException(status_code=400, detail="Payment not verified")

    if payment.status != "succeeded":
        logger.info("Вебхук ЮKassa: платёж %s в статусе %s — пропускаем", payment_id, payment.status)
        return {"ok": True, "status": payment.status}

    # 2) Данные тарифа и пользователя из метаданных платежа
    meta = obj.get("metadata") or payment.raw.get("metadata") or {}
    plan_id = str(meta.get("plan_id") or "")
    user_id_raw = meta.get("user_id")

    # Идемпотентность: платёж уже обработан?
    if db.query(Subscription).filter(Subscription.payment_id == payment_id).first() is not None:
        return {"ok": True, "note": "already processed"}

    selected = PLANS.get(plan_id)
    if selected is None:
        logger.warning("Вебхук ЮKassa: неизвестный тариф %r", plan_id)
        return {"ok": True, "note": "unknown plan"}

    user = db.get(User, int(user_id_raw)) if user_id_raw else None
    if user is None:
        logger.warning("Вебхук ЮKassa: пользователь не найден (%r)", user_id_raw)
        return {"ok": True, "note": "user not found"}

    # 3) Создаём пользователя в панели Remnawave
    expires_at = datetime.utcnow() + timedelta(days=selected["days"])
    username = f"vinni_{user.id}_{secrets.token_hex(3)}"
    squad_uuid = selected.get("squad_uuid")
    squad_uuids = [squad_uuid] if squad_uuid else None
    try:
        remna_user = get_client().create_user(
            username=username,
            expire_at=expires_at,
            squad_uuids=squad_uuids,
            hwid_device_limit=REMNAWAVE_HWID_LIMIT,
            traffic_limit_bytes=REMNAWAVE_TRAFFIC_LIMIT_BYTES,
            email=user.email,
        )
    except RemnawaveError as exc:
        logger.warning("Вебхук ЮKassa: ошибка Remnawave: %s", exc)
        # 500 — ЮKassa повторит уведомление позже
        raise HTTPException(status_code=500, detail="Remnawave error")

    # 4) Сохраняем подписку
    subscription = Subscription(
        user_id=user.id,
        uuid=new_uuid(),
        plan_name=selected["name"],
        owner_name=user.email,
        is_active=True,
        expires_at=expires_at,
        remnawave_uuid=remna_user.uuid,
        subscription_url=remna_user.subscription_url,
        payment_id=payment_id,
    )
    try:
        db.add(subscription)
        db.commit()
    except Exception:
        db.rollback()
        logger.exception("Вебхук ЮKassa: сбой записи подписки (payment=%s)", payment_id)
        raise HTTPException(status_code=500, detail="DB error")

    logger.info("Вебхук ЮKassa: подписка активирована (payment=%s, user=%s)", payment_id, user.id)
    return {"ok": True}
