"""Админ-панель: генерация ключей и таблица выданных подписок."""

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.config import SUB_BASE_URL
from app.database import get_db
from app.deps import require_admin
from app.flash import add_flash
from app.models import Subscription, User
from app.security import new_uuid
from app.templating import render

router = APIRouter(tags=["admin"])


@router.get("/admin")
def admin_page(
    request: Request,
    user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    subscriptions = (
        db.query(Subscription).order_by(Subscription.created_at.desc()).all()
    )
    return render(
        request,
        "admin.html",
        {
            "subscriptions": subscriptions,
            "sub_base_url": SUB_BASE_URL,
        },
    )


@router.post("/admin/keys")
def create_key(
    request: Request,
    name: str = Form(...),
    limit: str = Form(...),
    user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    name = name.strip()
    limit = limit.strip()
    if not name or not limit:
        add_flash(request, "Укажите имя и лимит.", "error")
        return RedirectResponse("/admin", status_code=303)

    subscription = Subscription(
        user_id=None,
        uuid=new_uuid(),
        plan_name=limit,
        owner_name=name,
        is_active=True,
        expires_at=None,  # бессрочно
    )
    db.add(subscription)
    db.commit()
    db.refresh(subscription)

    add_flash(
        request,
        f"Ключ для «{name}» создан: {SUB_BASE_URL}/{subscription.uuid}",
        "success",
    )
    return RedirectResponse("/admin", status_code=303)
