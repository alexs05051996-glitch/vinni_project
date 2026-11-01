"""Inline-клавиатуры бота."""

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


def ban_keyboard(remnawave_id: int, short_uuid: str) -> InlineKeyboardMarkup:
    """Кнопка «Забанить» под подозрительным аккаунтом."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🚫 Забанить",
                    callback_data=f"ban:{remnawave_id}:{short_uuid or '-'}",
                )
            ]
        ]
    )


def confirm_ban_keyboard(remnawave_id: int, short_uuid: str) -> InlineKeyboardMarkup:
    """Подтверждение бана."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✅ Подтвердить бан",
                    callback_data=f"ban_confirm:{remnawave_id}:{short_uuid or '-'}",
                ),
                InlineKeyboardButton(text="Отмена", callback_data="ban_cancel"),
            ]
        ]
    )
