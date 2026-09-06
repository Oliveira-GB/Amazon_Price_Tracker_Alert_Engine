import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class MessageHeader(BaseModel):
    trace_id: uuid.UUID = Field(default_factory=uuid.uuid4)
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    retry_count: int = Field(default=0, ge=0, le=10)


class WrappedMessage(BaseModel):
    header: MessageHeader = Field(default_factory=MessageHeader)
    payload: dict = Field(default_factory=dict)

    class Config:
        json_schema_extra = {
            "example": {
                "header": {
                    "trace_id": "550e8400-e29b-41d4-a716-446655440000",
                    "timestamp": "2026-09-05T10:00:00Z",
                    "retry_count": 0
                },
                "payload": {}
            }
        }
