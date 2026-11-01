"""Сбор отчёта: топ-5 по трафику и подозрительные аккаунты (>N IP за 24ч)."""

import logging
from typing import Optional

from app.services.remnawave import RemnawaveClient, RemnawaveError, get_client
from bot import config, texts

logger = logging.getLogger("vinni.bot.reports")


def _traffic_of(user: dict) -> int:
    """Использованный трафик пользователя (в байтах) из разных вариантов ответа."""
    traffic = user.get("userTraffic") or {}
    for key in ("usedTrafficBytes", "lifetimeUsedTrafficBytes"):
        value = traffic.get(key)
        if isinstance(value, (int, float)):
            return int(value)
    for key in ("usedTrafficBytes", "trafficUsedBytes"):
        value = user.get(key)
        if isinstance(value, (int, float)):
            return int(value)
    return 0


def human_bytes(num: int) -> str:
    value = float(num)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if value < 1024 or unit == "TB":
            return f"{value:.1f} {unit}"
        value /= 1024
    return f"{value:.1f} TB"


def build_report(client: Optional[RemnawaveClient] = None) -> tuple[str, list[dict]]:
    """Возвращает (текст_сводки, список_подозрительных)."""
    client = client or get_client()
    users = client.list_users()

    ranked = sorted(users, key=_traffic_of, reverse=True)[: config.TOP_TRAFFIC_LIMIT]
    parts = [texts.report_header(len(users)), texts.top_traffic_header()]
    if ranked:
        for idx, user in enumerate(ranked, 1):
            name = user.get("username") or user.get("shortUuid") or "?"
            parts.append(texts.top_traffic_line(idx, name, human_bytes(_traffic_of(user))))
    else:
        parts.append("— нет данных")

    suspicious: list[dict] = []
    for user in users:
        numeric_id = user.get("id")
        if numeric_id is None:
            continue
        try:
            ips = client.user_ip_addresses(int(numeric_id))
        except RemnawaveError as exc:
            logger.warning("Не удалось получить IP для %s: %s", numeric_id, exc)
            continue
        if len(ips) > config.SUSPICIOUS_IP_THRESHOLD:
            suspicious.append(
                {
                    "remnawave_id": int(numeric_id),
                    "short_uuid": user.get("shortUuid") or "",
                    "username": user.get("username") or "?",
                    "unique_ips": len(ips),
                }
            )

    return "\n".join(parts), suspicious
