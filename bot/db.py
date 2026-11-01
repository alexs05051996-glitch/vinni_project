"""Доступ к общей SQLite-БД (том + WAL) для бота."""

from app.database import Base, SessionLocal, engine  # noqa: F401  (реэкспорт)


def enable_wal() -> None:
    """Включает WAL и busy-timeout для безопасной работы сайта и бота параллельно."""
    if engine.dialect.name == "sqlite":
        with engine.connect() as conn:
            conn.exec_driver_sql("PRAGMA journal_mode=WAL")
            conn.exec_driver_sql("PRAGMA busy_timeout=5000")


def session():
    """Новая сессия SQLAlchemy."""
    return SessionLocal()
