"""Создание таблиц, лёгкие миграции и идемпотентный сид администратора."""

from sqlalchemy import inspect, text

from app.config import ADMIN_EMAIL, ADMIN_PASSWORD
from app.database import Base, SessionLocal, engine
from app.models import User
from app.security import hash_password

# Новые колонки, которые могли отсутствовать в старой SQLite-БД.
# Формат: {имя_таблицы: {имя_колонки: SQL-тип}}
_EXPECTED_COLUMNS: dict[str, dict[str, str]] = {
    "subscriptions": {
        "remnawave_uuid": "VARCHAR(36)",
        "subscription_url": "VARCHAR(512)",
        "payment_id": "VARCHAR(64)",
    },
    "users": {
        "has_used_trial": "BOOLEAN DEFAULT 0",
    },
}


def _ensure_columns() -> None:
    """Идемпотентно добавляет недостающие колонки (лёгкая миграция).

    Использует стандартный ``ALTER TABLE ADD COLUMN`` — совместимо с SQLite
    и PostgreSQL. БД не пересоздаётся, данные сохраняются.
    """
    inspector = inspect(engine)
    existing_tables = set(inspector.get_table_names())
    with engine.begin() as conn:
        for table, columns in _EXPECTED_COLUMNS.items():
            if table not in existing_tables:
                continue
            present = {col["name"] for col in inspector.get_columns(table)}
            for name, ddl_type in columns.items():
                if name not in present:
                    conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {name} {ddl_type}"))


def init_db() -> None:
    """Создаёт таблицы (если их нет), доводит схему и гарантирует наличие админа."""
    Base.metadata.create_all(bind=engine)
    _ensure_columns()

    db = SessionLocal()
    try:
        admin = db.query(User).filter(User.email == ADMIN_EMAIL).first()
        if admin is None:
            admin = User(
                email=ADMIN_EMAIL,
                password_hash=hash_password(ADMIN_PASSWORD),
                role="admin",
                balance=0.0,
            )
            db.add(admin)
            db.commit()
    finally:
        db.close()

