"""SQLAlchemy-модели приложения «ВИННИ»."""

from datetime import datetime

from sqlalchemy import (
    BigInteger,
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
    # Числовой id пользователя в панели Remnawave (нужен для бана/disable)
    remnawave_id = Column(Integer, nullable=True, index=True)
    subscription_url = Column(String(512), nullable=True)
    # Идентификатор платежа ЮKassa (для идемпотентности вебхука)
    payment_id = Column(String(64), nullable=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    user = relationship("User", back_populates="subscriptions")

    def __repr__(self) -> str:  # pragma: no cover - отладка
        return f"<Subscription id={self.id} uuid={self.uuid!r} plan={self.plan_name!r}>"


class TelegramUser(Base):
    """Связка Telegram ID с пользователем сайта (для уведомлений)."""

    __tablename__ = "telegram_users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    telegram_id = Column(BigInteger, unique=True, index=True, nullable=False)
    # NULL, пока аккаунт не привязан к сайту
    user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    tg_username = Column(String(64), nullable=True)
    notifications_enabled = Column(Boolean, default=True, nullable=False)
    is_bot_blocked = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    user = relationship("User")

    def __repr__(self) -> str:  # pragma: no cover - отладка
        return f"<TelegramUser telegram_id={self.telegram_id} user_id={self.user_id}>"


class TelegramLinkCode(Base):
    """Одноразовый код привязки Telegram к аккаунту сайта."""

    __tablename__ = "telegram_link_codes"

    id = Column(Integer, primary_key=True, autoincrement=True)
    code = Column(String(16), unique=True, index=True, nullable=False)
    user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    expires_at = Column(DateTime, nullable=False)
    used_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class ModerationEvent(Base):
    """Лог действий модерации (баны за шаринг подписки)."""

    __tablename__ = "moderation_events"

    id = Column(Integer, primary_key=True, autoincrement=True)
    remnawave_id = Column(Integer, nullable=True, index=True)
    short_uuid = Column(String(36), nullable=True)
    reason = Column(String(255), nullable=True)
    unique_ips = Column(Integer, nullable=True)
    action = Column(String(32), nullable=False, default="disable")
    tg_admin_id = Column(BigInteger, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
