import uuid
from datetime import datetime

import pytest
from pydantic import ValidationError

from schemas.base import MessageHeader, WrappedMessage


class TestMessageHeader:
    def test_message_header_valid(self):
        header = MessageHeader(
            trace_id=uuid.uuid4(),
            timestamp=datetime.utcnow(),
            retry_count=0,
        )
        assert header.retry_count == 0
        assert isinstance(header.trace_id, uuid.UUID)

    def test_message_header_default_retry_count(self):
        header = MessageHeader()
        assert header.retry_count == 0

    def test_message_header_retry_boundary_min(self):
        with pytest.raises(ValidationError) as exc_info:
            MessageHeader(retry_count=-1)
        assert "retry_count" in str(exc_info.value)

    def test_message_header_retry_boundary_max(self):
        with pytest.raises(ValidationError) as exc_info:
            MessageHeader(retry_count=11)
        assert "retry_count" in str(exc_info.value)

    def test_message_header_retry_valid_boundary_10(self):
        header = MessageHeader(retry_count=10)
        assert header.retry_count == 10

    def test_message_header_invalid_uuid(self):
        with pytest.raises(ValidationError):
            MessageHeader(trace_id="not-a-uuid")

    def test_message_header_valid_uuid_string(self):
        valid_uuid = "123e4567-e89b-12d3-a456-426614174000"
        header = MessageHeader(trace_id=valid_uuid)
        assert header.trace_id == uuid.UUID(valid_uuid)


class TestWrappedMessage:
    def test_wrapped_message_empty_payload(self):
        msg = WrappedMessage()
        assert msg.payload == {}

    def test_wrapped_message_nested_payload(self):
        msg = WrappedMessage(payload={"a": {"b": [1, 2, 3]}})
        assert msg.payload["a"]["b"] == [1, 2, 3]

    def test_wrapped_message_with_header(self):
        header = MessageHeader(retry_count=5)
        msg = WrappedMessage(header=header, payload={"key": "value"})
        assert msg.header.retry_count == 5
        assert msg.payload["key"] == "value"

    def test_wrapped_message_serialization(self):
        msg = WrappedMessage(
            header=MessageHeader(trace_id=uuid.uuid4()),
            payload={"test": "data"},
        )
        json_data = msg.model_dump_json()
        restored = WrappedMessage.model_validate_json(json_data)
        assert restored.payload == msg.payload
        assert restored.header.trace_id == msg.header.trace_id
