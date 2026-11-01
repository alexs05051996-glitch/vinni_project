"""Клиент API панели Remnawave.

Использует синхронный ``httpx.Client`` (приложение полностью синхронное).

Контракт создания пользователя (POST /api/users):
    headers: Authorization: Bearer <token>
    body:    { username, expireAt, hwidDeviceLimit, activeInternalSquads, trafficLimitBytes, ... }
    ответ:   201 { "response": { "uuid", "subscriptionUrl", ... } }

Если ``REMNAWAVE_ENABLED=false`` — работает mock-режим (без обращения к панели),
что удобно для локальных тестов.
"""

from __future__ import annotations

import logging
import uuid as _uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

import httpx

logger = logging.getLogger("vinni.remnawave")


class RemnawaveError(Exception):
    """Ошибка при обращении к API Remnawave."""


@dataclass
class RemnawaveUser:
    uuid: str
    short_uuid: str
    username: str
    subscription_url: str
    expire_at: Optional[str] = None
    # Числовой id пользователя в панели (для disable/enable/...)
    numeric_id: Optional[int] = None
    raw: dict[str, Any] = field(default_factory=dict)


def _to_iso_utc(dt: datetime) -> str:
    """Приводит datetime к формату Remnawave: 2026-12-01T00:00:00.000Z."""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    else:
        dt = dt.astimezone(timezone.utc)
    return dt.strftime("%Y-%m-%dT%H:%M:%S.") + f"{dt.microsecond // 1000:03d}Z"


class RemnawaveClient:
    def __init__(
        self,
        base_url: str,
        token: str,
        timeout: float = 15.0,
        enabled: bool = True,
        mock_base_url: str = "",
    ) -> None:
        self.base_url = (base_url or "").rstrip("/")
        self.token = token or ""
        self.timeout = timeout
        self.enabled = enabled
        self.mock_base_url = (mock_base_url or "").rstrip("/")

    @property
    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    def create_user(
        self,
        *,
        username: str,
        expire_at: datetime,
        squad_uuids: Optional[list[str]] = None,
        hwid_device_limit: int = 3,
        traffic_limit_bytes: int = 0,
        traffic_limit_strategy: str = "NO_RESET",
        email: Optional[str] = None,
        status: str = "ACTIVE",
        description: Optional[str] = None,
        tag: Optional[str] = None,
    ) -> RemnawaveUser:
        """Создаёт пользователя в панели и возвращает uuid + subscriptionUrl.

        Бросает ``RemnawaveError`` при любой проблеме (сеть, таймаут, статус >= 400,
        некорректный ответ). Вызывающий код при этом НЕ должен списывать баланс.
        """
        expire_iso = _to_iso_utc(expire_at)

        # --- Mock-режим для локальных тестов ---
        if not self.enabled:
            return self._mock_user(username, expire_iso)

        if not self.base_url or not self.token:
            raise RemnawaveError(
                "Remnawave включён, но не заданы REMNAWAVE_BASE_URL / REMNAWAVE_API_TOKEN."
            )

        payload: dict[str, Any] = {
            "username": username,
            "expireAt": expire_iso,
            "status": status,
            "trafficLimitBytes": traffic_limit_bytes,
            "trafficLimitStrategy": traffic_limit_strategy,
            "hwidDeviceLimit": hwid_device_limit,
        }
        if squad_uuids:
            payload["activeInternalSquads"] = list(squad_uuids)
        if email:
            payload["email"] = email
        if description:
            payload["description"] = description
        if tag:
            payload["tag"] = tag

        url = f"{self.base_url}/api/users"
        try:
            with httpx.Client(timeout=self.timeout) as client:
                response = client.post(url, json=payload, headers=self._headers)
        except httpx.HTTPError as exc:
            raise RemnawaveError(f"Не удалось подключиться к панели Remnawave: {exc}") from exc

        if response.status_code >= 400:
            raise RemnawaveError(
                f"API Remnawave вернуло {response.status_code}: {response.text[:300]}"
            )

        try:
            data = response.json()
        except ValueError as exc:
            raise RemnawaveError("Некорректный ответ API Remnawave (не JSON).") from exc

        body = data.get("response", data) if isinstance(data, dict) else {}
        # Разные версии панели возвращают идентификатор как uuid, shortUuid или id
        rw_uuid = body.get("uuid") or body.get("shortUuid")
        sub_url = body.get("subscriptionUrl")
        if not rw_uuid or not sub_url:
            raise RemnawaveError(
                "В ответе API нет идентификатора (uuid/shortUuid) или subscriptionUrl: "
                f"{body}"
            )

        numeric_id = body.get("id")
        return RemnawaveUser(
            uuid=str(rw_uuid),
            short_uuid=body.get("shortUuid", ""),
            username=body.get("username", username),
            subscription_url=sub_url,
            expire_at=body.get("expireAt", expire_iso),
            numeric_id=int(numeric_id) if numeric_id is not None else None,
            raw=body,
        )

    def _mock_user(self, username: str, expire_iso: str) -> RemnawaveUser:
        fake_uuid = str(_uuid.uuid4())
        base = self.mock_base_url or "https://sub.vinni.fyi"
        logger.warning(
            "Remnawave MOCK-режим (REMNAWAVE_ENABLED=false): фейковая подписка для %s",
            username,
        )
        return RemnawaveUser(
            uuid=fake_uuid,
            short_uuid=fake_uuid.replace("-", "")[:16],
            username=username,
            subscription_url=f"{base}/mock/{fake_uuid}",
            expire_at=expire_iso,
            numeric_id=int(_uuid.uuid4().int % 100000),
            raw={"mock": True, "username": username},
        )


    # --- данные для отчётов и модерации ---

    def _request(self, method: str, path: str, **kwargs: Any) -> Any:
        url = f"{self.base_url}{path}"
        try:
            with httpx.Client(timeout=self.timeout) as client:
                response = client.request(method, url, headers=self._headers, **kwargs)
        except httpx.HTTPError as exc:
            raise RemnawaveError(f"Не удалось подключиться к панели Remnawave: {exc}") from exc
        if response.status_code >= 400:
            raise RemnawaveError(f"API Remnawave вернуло {response.status_code}: {response.text[:300]}")
        try:
            return response.json()
        except ValueError as exc:
            raise RemnawaveError("Некорректный ответ API Remnawave (не JSON).") from exc

    @staticmethod
    def _unwrap(data: Any) -> Any:
        return data.get("response", data) if isinstance(data, dict) else data

    def list_users(self) -> list[dict]:
        """Список пользователей панели (с трафиком, если он есть в ответе)."""
        if not self.enabled:
            return []
        data = self._unwrap(self._request("GET", "/api/users"))
        return data if isinstance(data, list) else []

    def find_user(
        self,
        *,
        numeric_id: Optional[int] = None,
        short_uuid: Optional[str] = None,
        username: Optional[str] = None,
    ) -> Optional[dict]:
        if not self.enabled:
            return None
        if numeric_id is not None:
            data = self._unwrap(self._request("GET", f"/api/users/{numeric_id}"))
        elif short_uuid:
            data = self._unwrap(self._request("GET", f"/api/users/by-short-uuid/{short_uuid}"))
        elif username:
            data = self._unwrap(self._request("GET", f"/api/users/by-username/{username}"))
        else:
            return None
        return data if isinstance(data, dict) else None

    def disable_user(self, numeric_id: int) -> dict:
        """Блокирует пользователя в панели (бан)."""
        if not self.enabled:
            logger.warning("Remnawave MOCK: disable user %s", numeric_id)
            return {"mock": True, "id": numeric_id, "status": "DISABLED"}
        data = self._unwrap(self._request("POST", f"/api/users/{numeric_id}/actions/disable"))
        return data if isinstance(data, dict) else {}

    def user_ip_addresses(self, numeric_id: int, wait_seconds: float = 8.0) -> list[str]:
        """Уникальные IP пользователя через асинхронную job connections."""
        if not self.enabled:
            return []
        import time

        data = self._unwrap(self._request("POST", f"/api/connections/by-user/{numeric_id}"))
        job = data if isinstance(data, dict) else {}
        job_id = job.get("jobId") or job.get("job_id")
        if not job_id:
            return []

        deadline = time.time() + wait_seconds
        while time.time() < deadline:
            payload = self._unwrap(self._request("GET", f"/api/connections/by-user/{job_id}"))
            payload = payload if isinstance(payload, dict) else {}
            is_done = payload.get("isCompleted", payload.get("is_done"))
            if is_done:
                connections = payload.get("connections") or payload.get("data") or []
                ips: set[str] = set()
                for item in connections:
                    if not isinstance(item, dict):
                        continue
                    ip = item.get("ip") or item.get("ipAddress") or (item.get("metadata") or {}).get("ip")
                    if ip:
                        ips.add(str(ip))
                return sorted(ips)
            time.sleep(1.0)
        logger.warning("connections job %s не завершилась за %ss", job_id, wait_seconds)
        return []


def get_client() -> RemnawaveClient:
    """Собирает клиент из настроек приложения."""
    from app import config

    return RemnawaveClient(
        base_url=config.REMNAWAVE_BASE_URL,
        token=config.REMNAWAVE_API_TOKEN,
        timeout=config.REMNAWAVE_TIMEOUT,
        enabled=config.REMNAWAVE_ENABLED,
        mock_base_url=config.SUB_BASE_URL,
    )
