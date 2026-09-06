import uuid
from datetime import datetime
from enum import Enum

from sqlalchemy import DateTime, String, Text, Index, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from models.base import Base, TimestampMixin, UUIDMixin


class ProductStatus(str, Enum):
    ACTIVE = "ACTIVE"
    PAUSED = "PAUSED"
    UNAVAILABLE = "UNAVAILABLE"
    IDLE = "IDLE"


class Product(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "products"

    asin: Mapped[str] = mapped_column(
        String(20),
        unique=True,
        nullable=False,
        index=True,
    )
    title: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    url: Mapped[str | None] = mapped_column(
        String(512),
        nullable=True,
    )
    image_url: Mapped[str | None] = mapped_column(
        String(512),
        nullable=True,
    )
    status: Mapped[ProductStatus] = mapped_column(
        String(20),
        default=ProductStatus.IDLE,
        nullable=False,
        index=True,
    )
    last_checked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    last_price_full: Mapped[float | None] = mapped_column(
        nullable=True,
    )
    last_price_discount: Mapped[float | None] = mapped_column(
        nullable=True,
    )
    all_time_low: Mapped[float | None] = mapped_column(
        nullable=True,
    )
    failure_count: Mapped[int] = mapped_column(
        default=0,
        nullable=False,
    )

    __table_args__ = (
        Index("ix_products_status_checked", "status", "last_checked_at"),
    )

    subscriptions: Mapped[list["UserProduct"]] = relationship(
        "UserProduct",
        back_populates="product",
        cascade="all, delete-orphan",
    )
    price_history: Mapped[list["PriceHistory"]] = relationship(
        "PriceHistory",
        back_populates="product",
        cascade="all, delete-orphan",
    )


from models.user_product import UserProduct
from models.price_history import PriceHistory
