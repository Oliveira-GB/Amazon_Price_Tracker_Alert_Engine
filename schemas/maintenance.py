import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class UserBlockedEvent(BaseModel):
    event_id: str = Field(..., description="Unique event identifier")
    user_id: uuid.UUID = Field(..., description="Blocked user UUID")
    telegram_chat_id: str = Field(..., description="Telegram chat ID")
    reason: str = Field(..., description="Block reason")
    trace_id: uuid.UUID = Field(default_factory=uuid.uuid4)
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    retry_count: int = Field(default=0, ge=0, le=10)

    class Config:
        json_schema_extra = {
            "example": {
                "event_id": "blocked-aabb-ccdd",
                "user_id": "123e4567-e89b-12d3-a456-426614174000",
                "telegram_chat_id": "987654321",
                "reason": "bot_blocked",
                "trace_id": "550e8400-e29b-41d4-a716-446655440000",
                "timestamp": "2026-09-05T15:00:00Z",
                "retry_count": 0
            }
        }


class HardDeleteCommand(BaseModel):
    event_id: str = Field(..., description="Unique event identifier")
    user_id: uuid.UUID = Field(..., description="User to delete")
    telegram_chat_id: str = Field(..., description="Telegram chat ID")
    initiated_by: str = Field(default="system", description="What triggered the deletion")
    trace_id: uuid.UUID = Field(default_factory=uuid.uuid4)
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    retry_count: int = Field(default=0, ge=0, le=10)

    class Config:
        json_schema_extra = {
            "example": {
                "event_id": "delete-001122",
                "user_id": "123e4567-e89b-12d3-a456-426614174000",
                "telegram_chat_id": "987654321",
                "initiated_by": "telegram_403",
                "trace_id": "550e8400-e29b-41d4-a716-446655440000",
                "timestamp": "2026-09-05T15:00:00Z",
                "retry_count": 0
            }
        }
