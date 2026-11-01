"""Клиент API ЮKassa (приём платежей: СБП, QR, банковские карты).

Синхронный ``httpx.Client``.

Режимы:
    * Реальный — если заданы YOOKASSA_SHOP_ID и YOOKASSA_SECRET_KEY.
      Запросы идут на https://api.yookassa.ru/v3/payments (Basic-аутентификация).
    * Mock — если ключей нет: фейковый платёж с confirmation_url
      = https://yookassa.ru/test-payment (для локальных тестов).
"""

from __future__ import annotations

import logging
import uuid as _uuid
from dataclasses import dataclass, field
from typing import Any, Optional

import httpx

logger = logging.getLogger("vinni.yookassa")

MOCK_CONFIRMATION_URL = "https://yookassa.ru/test-payment"


class YooKassaError(Exception):
    """Ошибка при обращении к API ЮKassa."""


@dataclass
class Payment:
    payment_id: str
    status: str
    confirmation_url: Optional[str] = None
    amount: Optional[float] = None
    raw: dict[str, Any] = field(default_factory=dict)


def _amount_value(data: dict[str, Any]) -> Optional[float]:
    try:
        return float(data["amount"]["value"])
    except (KeyError, TypeError, ValueError):
        return None


class YooKassaClient:
    def __init__(
        self,
        shop_id: str,
        secret_key: str,
        return_url: str,
        api_url: str = "https://api.yookassa.ru/v3",
        timeout: float = 15.0,
        enabled: bool = True,
    ) -> None:
        self.shop_id = shop_id or ""
        self.secret_key = secret_key or ""
        self.return_url = return_url or ""
        self.api_url = (api_url or "https://api.yookassa.ru/v3").rstrip("/")
        self.timeout = timeout
        # Реальный режим возможен только при наличии ключей
        self.enabled = bool(enabled and self.shop_id and self.secret_key)

    @property
    def is_mock(self) -> bool:
        return not self.enabled

    def create_payment(
        self,
        amount: float,
        plan_id: str,
        user_id: int,
        description: Optional[str] = None,
        use_sbp: bool = False,
    ) -> Payment:
        """Создаёт платёж и возвращает confirmation_url + payment_id."""
        if self.is_mock:
            return self._mock_payment(amount, plan_id, user_id, use_sbp)

        payload: dict[str, Any] = {
            "amount": {"value": f"{float(amount):.2f}", "currency": "RUB"},
            "capture": True,
            "confirmation": {"type": "redirect", "return_url": self.return_url},
            "description": description or f"Оплата подписки ({plan_id})",
            "metadata": {"plan_id": str(plan_id), "user_id": str(user_id)},
        }
        if use_sbp:
            # Оплата через СБП (на странице ЮKassa покажется QR-код)
            payload["payment_method_data"] = {"type": "sbp"}

        headers = {"Idempotence-Key": str(_uuid.uuid4())}
        try:
            with httpx.Client(timeout=self.timeout) as client:
                response = client.post(
                    f"{self.api_url}/payments",
                    json=payload,
                    auth=(self.shop_id, self.secret_key),
                    headers=headers,
                )
        except httpx.HTTPError as exc:
            raise YooKassaError(f"Не удалось подключиться к ЮKassa: {exc}") from exc

        if response.status_code >= 400:
            raise YooKassaError(f"ЮKassa вернула {response.status_code}: {response.text[:300]}")

        data = response.json()
        confirmation = data.get("confirmation") or {}
        return Payment(
            payment_id=data.get("id", ""),
            status=data.get("status", ""),
            confirmation_url=confirmation.get("confirmation_url"),
            amount=_amount_value(data),
            raw=data,
        )

    def get_payment(self, payment_id: str) -> Payment:
        """Возвращает статус платежа (для проверки вебхука)."""
        if self.is_mock:
            return Payment(
                payment_id=payment_id,
                status="succeeded",
                confirmation_url=MOCK_CONFIRMATION_URL,
                raw={"mock": True, "id": payment_id, "status": "succeeded"},
            )

        try:
            with httpx.Client(timeout=self.timeout) as client:
                response = client.get(
                    f"{self.api_url}/payments/{payment_id}",
                    auth=(self.shop_id, self.secret_key),
                )
        except httpx.HTTPError as exc:
            raise YooKassaError(f"Не удалось подключиться к ЮKassa: {exc}") from exc

        if response.status_code >= 400:
            raise YooKassaError(f"ЮKassa вернула {response.status_code}: {response.text[:300]}")

        data = response.json()
        confirmation = data.get("confirmation") or {}
        return Payment(
            payment_id=data.get("id", payment_id),
            status=data.get("status", ""),
            confirmation_url=confirmation.get("confirmation_url"),
            amount=_amount_value(data),
            raw=data,
        )

    def _mock_payment(self, amount: float, plan_id: str, user_id: int, use_sbp: bool) -> Payment:
        payment_id = f"mock-{user_id}-{plan_id}-{_uuid.uuid4().hex[:8]}"
        logger.warning(
            "ЮKassa MOCK-режим: создан фейковый платёж %s (СБП=%s). Ключи не заданы.",
            payment_id,
            use_sbp,
        )
        return Payment(
            payment_id=payment_id,
            status="pending",
            confirmation_url=MOCK_CONFIRMATION_URL,
            amount=float(amount),
            raw={
                "mock": True,
                "id": payment_id,
                "status": "pending",
                "amount": {"value": f"{float(amount):.2f}", "currency": "RUB"},
                "metadata": {"plan_id": str(plan_id), "user_id": str(user_id)},
            },
        )


def get_yookassa_client() -> YooKassaClient:
    """Собирает клиент из настроек приложения."""
    from app import config

    return YooKassaClient(
        shop_id=config.YOOKASSA_SHOP_ID,
        secret_key=config.YOOKASSA_SECRET_KEY,
        return_url=config.YOOKASSA_RETURN_URL,
        api_url=config.YOOKASSA_API_URL,
        enabled=config.YOOKASSA_ENABLED,
    )