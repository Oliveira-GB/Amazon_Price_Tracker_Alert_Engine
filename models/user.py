from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from models.base import Base, TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from models.user_product import UserProduct


class User(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "users"

    telegram_chat_id: Mapped[str] = mapped_column(
        String(64),
        unique=True,
        nullable=False,
        index=True,
    )
    quota_limit: Mapped[int] = mapped_column(
        Integer,
        default=50,
        nullable=False,
    )
    is_active: Mapped[bool] = mapped_column(
        default=True,
        nullable=False,
    )
    last_seen_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    subscriptions: Mapped[list[UserProduct]] = relationship(
        "UserProduct",
        back_populates="user",
        cascade="all, delete-orphan",
    )
