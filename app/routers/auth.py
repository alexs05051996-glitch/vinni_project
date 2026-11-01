"""Регистрация, вход и выход."""

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_optional_user
from app.flash import add_flash
from app.models import User
from app.ratelimit import (
    LOGIN_LIMIT,
    LOGIN_LIMIT_LONG,
    REGISTER_LIMIT,
    REGISTER_LIMIT_LONG,
    limiter,
)
from app.schemas import RegistrationIn
from app.security import hash_password, verify_password
from app.templating import render

router = APIRouter(tags=["auth"])


@router.get("/register")
def register_page(
    request: Request,
    db: Session = Depends(get_db),
    user: User | None = Depends(get_optional_user),
):
    if user is not None:
        return RedirectResponse("/dashboard", status_code=303)
    return render(request, "auth/register.html")


@router.post("/register")
@limiter.limit(REGISTER_LIMIT)
@limiter.limit(REGISTER_LIMIT_LONG)
def register(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db),
    user: User | None = Depends(get_optional_user),
):
    if user is not None:
        return RedirectResponse("/dashboard", status_code=303)

    # Жёсткая валидация через Pydantic-схему (пароль min_length=8, корректный email)
    try:
        data = RegistrationIn(email=email, password=password)
    except ValidationError as exc:
        fields = {err["loc"][0] for err in exc.errors()}
        if "password" in fields:
            add_flash(request, "Пароль должен содержать не менее 8 символов.", "error")
        else:
            add_flash(request, "Укажите корректный email.", "error")
        return RedirectResponse("/register", status_code=303)

    email = data.email
    password = data.password

    existing = db.query(User).filter(User.email == email).first()
    if existing is not None:
        add_flash(request, "Пользователь с таким email уже зарегистрирован.", "error")
        return RedirectResponse("/register", status_code=303)

    new_user = User(
        email=email,
        password_hash=hash_password(password),
        role="user",
        balance=0.0,
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    request.session["user_id"] = new_user.id
    add_flash(request, "Регистрация успешна. Добро пожаловать!", "success")
    return RedirectResponse("/dashboard", status_code=303)


@router.get("/login")
def login_page(
    request: Request,
    db: Session = Depends(get_db),
    user: User | None = Depends(get_optional_user),
):
    if user is not None:
        return RedirectResponse("/dashboard", status_code=303)
    return render(request, "auth/login.html")


@router.post("/login")
@limiter.limit(LOGIN_LIMIT)
@limiter.limit(LOGIN_LIMIT_LONG)
def login(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db),
    user: User | None = Depends(get_optional_user),
):
    if user is not None:
        return RedirectResponse("/dashboard", status_code=303)

    email = email.strip().lower()
    found = db.query(User).filter(User.email == email).first()
    if found is None or not verify_password(password, found.password_hash):
        add_flash(request, "Неверный email или пароль.", "error")
        return RedirectResponse("/login", status_code=303)

    request.session["user_id"] = found.id
    add_flash(request, f"С возвращением, {found.email}!", "success")
    return RedirectResponse("/dashboard", status_code=303)


@router.get("/logout")
def logout(request: Request):
    request.session.clear()
    return RedirectResponse("/", status_code=303)
