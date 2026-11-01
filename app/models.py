"""SQLAlchemy-модели приложения «ВИННИ»."""

from datetime import datetime

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
)
from sqlalchemy.orm import relationship

from app.database import Base


class User(Base):
    """Пользователь сервиса."""

    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    email = Column(String(255), unique=True, index=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    # "user" или "admin"
    role = Column(String(20), default="user", nullable=False)
    balance = Column(Float, default=0.0, nullable=False)
    # Флаг: использовал ли пользователь пробный период
    has_used_trial = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    subscriptions = relationship(
        "Subscription",
        back_populates="user",
        passive_deletes=True,
    )

    def __repr__(self) -> str:  # pragma: no cover - отладка
        return f"<User id={self.id} email={self.email!r} role={self.role}>"


class Subscription(Base):
    """Подписка (ключ доступа), выданная пользователю или админом вручную."""

    __tablename__ = "subscriptions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    # NULL для «ручных» ключей, созданных админом без привязки к аккаунту
    user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    uuid = Column(String(36), unique=True, index=True, nullable=False)
    # Название тарифа/лимита, напр. "50 ГБ" или "1 месяц"
    plan_name = Column(String(64), nullable=False)
    # «Имя» из админки (напр. "Вася") для ручных ключей
    owner_name = Column(String(64), nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    # NULL = бессрочно (для ручных ключей)
    expires_at = Column(DateTime, nullable=True)
    # Данные из панели Remnawave (для подписок, созданных через покупку)
    remnawave_uuid = Column(String(36), nullable=True, index=True)
    subscription_url = Column(String(512), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    user = relationship("User", back_populates="subscriptions")

    def __repr__(self) -> str:  # pragma: no cover - отладка
        return f"<Subscription id={self.id} uuid={self.uuid!r} plan={self.plan_name!r}>"
