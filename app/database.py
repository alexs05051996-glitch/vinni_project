"""Настройка подключения к БД и фабрика сессий (SQLAlchemy).

Архитектура рассчитана на лёгкий переход на PostgreSQL: достаточно поменять
переменную окружения DATABASE_URL — код моделей менять не нужно.
"""

from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

from app.config import DATABASE_URL

# SQLite требует особого аргумента для многопоточного доступа
connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}

engine = create_engine(
    DATABASE_URL,
    connect_args=connect_args,
    future=True,
)

SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False,
    future=True,
)

Base = declarative_base()


def get_db():
    """FastAPI-зависимость: отдаёт сессию БД и гарантированно закрывает её."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
