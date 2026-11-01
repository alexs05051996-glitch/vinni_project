"""Pydantic-схемы для валидации пользовательского ввода."""

import re

from pydantic import BaseModel, Field, field_validator

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class RegistrationIn(BaseModel):
    """Валидация формы регистрации: email + пароль (не менее 8 символов)."""

    email: str = Field(...)
    # Жёсткое ограничение: сайт не должен пропускать короткие пароли
    password: str = Field(..., min_length=8)

    @field_validator("email")
    @classmethod
    def _validate_email(cls, value: str) -> str:
        value = (value or "").strip().lower()
        if not _EMAIL_RE.match(value):
            raise ValueError("Укажите корректный email")
        return value