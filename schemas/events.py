import uuid
from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field


class AlertType(StrEnum):
    TARGET_PRICE = "target_price"
    ALL_TIME_LOW = "all_time_low"
    SYSTEM_MESSAGE = "system_message"


class PriceUpdatedEvent(BaseModel):
    event_id: str = Field(..., description="Unique event identifier")
    asin: str = Field(..., min_length=10, max_length=10)
    product_id: uuid.UUID = Field(...)
    price_full: float | None = Field(None, ge=0)
    price_discount: float | None = Field(None, ge=0)
    is_out_of_stock: bool = Field(False)
    previous_price_full: float | None = Field(None, ge=0)
    previous_price_discount: float | None = Field(None, ge=0)
    trace_id: uuid.UUID = Field(default_factory=uuid.uuid4)
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    retry_count: int = Field(default=0, ge=0, le=10)

    class Config:
        json_schema_extra = {
            "example": {
                "event_id": "price-aabb-ccdd",
                "asin": "B08ABC1234",
                "product_id": "123e4567-e89b-12d3-a456-426614174000",
                "price_full": 499.99,
                "price_discount": 399.99,
                "is_out_of_stock": False,
                "previous_price_full": 599.99,
                "previous_price_discount": 499.99,
                "trace_id": "550e8400-e29b-41d4-a716-446655440000",
                "timestamp": "2026-09-05T14:00:00Z",
                "retry_count": 0
            }
        }


class AlertTriggeredEvent(BaseModel):
    event_id: str = Field(..., description="Unique event identifier")
    alert_type: AlertType = Field(..., description="Type of alert")
    user_id: uuid.UUID = Field(..., description="User UUID")
    telegram_chat_id: str = Field(..., description="Telegram chat ID")
    product_id: uuid.UUID = Field(..., description="Product UUID")
    asin: str = Field(..., min_length=10, max_length=10)
    title: str | None = Field(None, max_length=200)
    image_url: str | None = Field(None)
    url: str | None = Field(None)
    target_price: float | None = Field(None, ge=0)
    current_price: float = Field(..., ge=0)
    previous_price: float | None = Field(None, ge=0)
    message: str = Field(..., max_length=1000)
    trace_id: uuid.UUID = Field(default_factory=uuid.uuid4)
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    retry_count: int = Field(default=0, ge=0, le=10)

    class Config:
        json_schema_extra = {
            "example": {
                "event_id": "alert-001122",
                "alert_type": "target_price",
                "user_id": "123e4567-e89b-12d3-a456-426614174000",
                "telegram_chat_id": "987654321",
                "product_id": "123e4567-e89b-12d3-a456-426614174000",
                "asin": "B08ABC1234",
                "title": "Samsung SSD 1TB",
                "image_url": "https://amazon.com/image.jpg",
                "url": "https://amazon.com.br/dp/B08ABC1234",
                "target_price": 350.00,
                "current_price": 339.99,
                "previous_price": 499.99,
                "message": "Price dropped to R$ 339.99!",
                "trace_id": "550e8400-e29b-41d4-a716-446655440000",
                "timestamp": "2026-09-05T14:30:00Z",
                "retry_count": 0
            }
        }
