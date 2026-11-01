"""Покупка тарифов, пополнение баланса, оплата (заглушка) и страница подписки."""

import logging
import secrets
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, Form, HTTPException, Request
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
)
from app.database import get_db
from app.deps import get_optional_user, require_user
from app.flash import add_flash
from app.models import Subscription, User
from app.security import new_uuid
from app.ratelimit import trial_guard
from app.services.remnawave import RemnawaveError, get_client
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


@router.post("/dashboard/buy")
def buy(
    request: Request,
    plan: str = Form(...),
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
):
    selected = PLANS.get(plan)
    if selected is None:
        add_flash(request, "Неизвестный тариф.", "error")
        return RedirectResponse("/dashboard", status_code=303)

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
