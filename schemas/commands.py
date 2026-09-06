import uuid
from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field


class MessageType(StrEnum):
    ITEM_VALIDATION_COMMAND = "item_validation_command"
    SCRAPE_COMMAND = "scrape_command"
    PRICE_UPDATED_EVENT = "price_updated_event"
    ALERT_TRIGGERED_EVENT = "alert_triggered_event"
    USER_BLOCKED_EVENT = "user_blocked_event"
    HARD_DELETE_COMMAND = "hard_delete_command"
    SYSTEM_MESSAGE = "system_message"


class ItemValidationCommand(BaseModel):
    event_id: str = Field(..., description="Unique event identifier")
    telegram_chat_id: str = Field(..., description="User's Telegram chat ID")
    raw_url: str = Field(..., description="Raw URL submitted by user")
    target_price: float | None = Field(None, description="Optional target price")
    alert_on_all_time_low: bool = Field(False, description="Alert on all-time low")
    trace_id: uuid.UUID = Field(default_factory=uuid.uuid4)
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    retry_count: int = Field(default=0, ge=0, le=10)

    class Config:
        json_schema_extra = {
            "example": {
                "event_id": "val-1122-ccdd",
                "telegram_chat_id": "987654321",
                "raw_url": "https://amzn.to/xyz",
                "target_price": 299.99,
                "alert_on_all_time_low": False,
                "trace_id": "550e8400-e29b-41d4-a716-446655440000",
                "timestamp": "2026-09-05T09:50:00Z",
                "retry_count": 0
            }
        }


class ScrapeCommand(BaseModel):
    event_id: str = Field(..., description="Unique event identifier")
    asin: str = Field(..., min_length=10, max_length=10, description="Amazon ASIN")
    product_id: uuid.UUID = Field(..., description="Internal product UUID")
    priority: int = Field(default=5, ge=1, le=10, description="Priority 1-10")
    trace_id: uuid.UUID = Field(default_factory=uuid.uuid4)
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    retry_count: int = Field(default=0, ge=0, le=10)

    class Config:
        json_schema_extra = {
            "example": {
                "event_id": "scrape-aabb-ccdd",
                "asin": "B08ABC1234",
                "product_id": "123e4567-e89b-12d3-a456-426614174000",
                "priority": 7,
                "trace_id": "550e8400-e29b-41d4-a716-446655440000",
                "timestamp": "2026-09-05T12:00:00Z",
                "retry_count": 0
            }
        }
