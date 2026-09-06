from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Index, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from models.product import Product
    from models.user import User


class UserProduct(Base, TimestampMixin):
    __tablename__ = "user_products"

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
    )
    product_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("products.id", ondelete="CASCADE"),
        primary_key=True,
    )
    target_price: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
    )
    alert_on_all_time_low: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )
    last_notified_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )

    __table_args__ = (
        UniqueConstraint("user_id", "product_id", name="uq_user_product"),
        Index("ix_user_products_user_active", "user_id", "is_active"),
    )

    user: Mapped[User] = relationship(
        "User",
        back_populates="subscriptions",
    )
    product: Mapped[Product] = relationship(
        "Product",
        back_populates="subscriptions",
    )
