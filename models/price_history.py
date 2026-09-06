import uuid
from datetime import datetime

from sqlalchemy import ForeignKey, DateTime, Float, Boolean, Index, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from models.base import Base, TimestampMixin


class PriceHistory(Base, TimestampMixin):
    __tablename__ = "price_history"

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True,
        default=uuid.uuid4,
    )
    product_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("products.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    price_full: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
    )
    price_discount: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
    )
    is_discounted: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )
    is_out_of_stock: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )
    scraped_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        index=True,
    )

    __table_args__ = (
        Index("ix_price_history_product_scraped", "product_id", "scraped_at"),
    )

    product: Mapped["Product"] = relationship(
        "Product",
        back_populates="price_history",
    )


from models.product import Product
