"""Планировщик: отчёт администратору раз в N часов."""

import asyncio
import logging

from aiogram import Bot
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from bot import config, texts
from bot.keyboards import ban_keyboard
from bot.services.reports import build_report

logger = logging.getLogger("vinni.bot.scheduler")


async def send_report(bot: Bot) -> None:
    """Собирает и отправляет отчёт администратору (+ кнопки «Забанить»)."""
    if not config.ADMIN_TELEGRAM_ID:
        logger.warning("ADMIN_TELEGRAM_ID не задан — отчёт не отправлен")
        return

    try:
        summary, suspicious = await asyncio.to_thread(build_report)
    except Exception:  # noqa: BLE001
        logger.exception("Не удалось собрать отчёт")
        return

    text = summary
    if suspicious:
        text += texts.suspicious_header(len(suspicious), config.SUSPICIOUS_IP_THRESHOLD)
        for item in suspicious:
            text += "\n" + texts.suspicious_line(
                item["username"], item["remnawave_id"], item["unique_ips"]
            )

    await bot.send_message(config.ADMIN_TELEGRAM_ID, text)

    # Отдельным сообщением — кнопка бана под каждым подозрительным аккаунтом
    for item in suspicious:
        await bot.send_message(
            config.ADMIN_TELEGRAM_ID,
            f"🚫 <code>{item['username']}</code> — {item['unique_ips']} IP",
            reply_markup=ban_keyboard(item["remnawave_id"], item["short_uuid"]),
        )


def setup_scheduler(bot: Bot) -> AsyncIOScheduler:
    scheduler = AsyncIOScheduler(timezone="UTC")
    scheduler.add_job(
        send_report,
        "interval",
        hours=config.REPORT_INTERVAL_HOURS,
        args=[bot],
    )
    scheduler.start()
    return scheduler
