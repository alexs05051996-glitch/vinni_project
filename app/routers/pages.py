"""Публичные страницы: лендинг и личный кабинет."""

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.config import IOS_CLIENTS, PLANS, TOPUP_AMOUNT
from app.database import get_db
from app.deps import get_optional_user, require_user
from app.models import Subscription, User
from app.templating import render

router = APIRouter(tags=["pages"])


@router.get("/")
def landing(
    request: Request,
    user: User | None = Depends(get_optional_user),
):
    return render(request, "landing.html", {"plans": PLANS, "ios_clients": IOS_CLIENTS})


@router.get("/dashboard")
def dashboard(
    request: Request,
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
):
    subscriptions = (
        db.query(Subscription)
        .filter(Subscription.user_id == user.id)
        .order_by(Subscription.created_at.desc())
        .all()
    )
    return render(
        request,
        "dashboard.html",
        {
            "plans": PLANS,
            "subscriptions": subscriptions,
            "topup_amount": TOPUP_AMOUNT,
        },
    )


@router.get("/terms")
def terms_page(
    request: Request,
    user: User | None = Depends(get_optional_user),
):
    """Публичная оферта (для модерации платёжной системы)."""
    return render(request, "terms.html")


@router.get("/privacy")
def privacy_page(
    request: Request,
    user: User | None = Depends(get_optional_user),
):
    """Политика конфиденциальности."""
    return render(request, "privacy.html")
