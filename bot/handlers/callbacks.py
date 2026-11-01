"""Inline-кнопки: подтверждение и выполнение бана."""

import logging

from aiogram import F, Router
from aiogram.types import CallbackQuery

from app.models import ModerationEvent
from app.services.remnawave import RemnawaveError, get_client
from bot import config, texts
from bot.db import session
from bot.keyboards import confirm_ban_keyboard

logger = logging.getLogger("vinni.bot.callbacks")

router = Router()


@router.callback_query(F.data.startswith("ban:"))
async def ask_confirm(callback: CallbackQuery) -> None:
    _, remnawave_id, short_uuid = callback.data.split(":", 2)
    await callback.message.edit_reply_markup(
        reply_markup=confirm_ban_keyboard(int(remnawave_id), short_uuid)
    )
    await callback.answer("Подтвердите бан")


@router.callback_query(F.data == "ban_cancel")
async def cancel(callback: CallbackQuery) -> None:
    await callback.message.edit_reply_markup(reply_markup=None)
    await callback.answer("Отменено")


@router.callback_query(F.data.startswith("ban_confirm:"))
async def do_ban(callback: CallbackQuery) -> None:
    _, remnawave_id, short_uuid = callback.data.split(":", 2)
    numeric_id = int(remnawave_id)

    try:
        get_client().disable_user(numeric_id)
    except RemnawaveError as exc:
        logger.warning("Ошибка бана %s: %s", numeric_id, exc)
        await callback.answer("Ошибка", show_alert=False)
        await callback.message.answer(texts.ban_error(str(exc)))
        return

    with session() as db:
        db.add(
            ModerationEvent(
                remnawave_id=numeric_id,
                short_uuid=short_uuid if short_uuid != "-" else None,
                reason=f">{config.SUSPICIOUS_IP_THRESHOLD} IP за 24ч",
                unique_ips=getattr(callback, "_unique_ips", None),
                action="disable",
                tg_admin_id=callback.from_user.id,
            )
        )
        db.commit()

    await callback.message.edit_reply_markup(reply_markup=None)
    await callback.message.answer(texts.ban_ok(short_uuid or str(numeric_id), numeric_id))
    await callback.answer("Забанен")
