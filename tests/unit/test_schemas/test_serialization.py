import uuid
from datetime import datetime

from schemas.base import MessageHeader, WrappedMessage
from schemas.commands import ItemValidationCommand, ScrapeCommand
from schemas.events import AlertTriggeredEvent, AlertType, PriceUpdatedEvent
from schemas.maintenance import HardDeleteCommand, UserBlockedEvent


class TestSerializationRoundtrips:
    def test_message_header_json_roundtrip(self):
        original = MessageHeader(
            trace_id=uuid.uuid4(),
            timestamp=datetime(2026, 9, 6, 10, 0, 0),
            retry_count=5,
        )
        json_str = original.model_dump_json()
        restored = MessageHeader.model_validate_json(json_str)
        assert restored.trace_id == original.trace_id
        assert restored.retry_count == original.retry_count

    def test_wrapped_message_json_roundtrip(self):
        original = WrappedMessage(
            header=MessageHeader(retry_count=3),
            payload={"key": "value", "nested": {"a": 1}},
        )
        json_str = original.model_dump_json()
        restored = WrappedMessage.model_validate_json(json_str)
        assert restored.payload == original.payload
        assert restored.header.retry_count == 3

    def test_item_validation_command_json_roundtrip(self):
        original = ItemValidationCommand(
            event_id="val-123",
            telegram_chat_id="123456",
            raw_url="https://amazon.com.br/dp/B08ABC1234",
            target_price=299.99,
            alert_on_all_time_low=True,
        )
        json_str = original.model_dump_json()
        restored = ItemValidationCommand.model_validate_json(json_str)
        assert restored.event_id == original.event_id
        assert restored.target_price == original.target_price
        assert restored.alert_on_all_time_low == original.alert_on_all_time_low

    def test_scrape_command_json_roundtrip(self):
        product_id = uuid.uuid4()
        original = ScrapeCommand(
            event_id="scrape-123",
            asin="B08ABC1234",
            product_id=product_id,
            priority=8,
        )
        json_str = original.model_dump_json()
        restored = ScrapeCommand.model_validate_json(json_str)
        assert restored.asin == original.asin
        assert restored.product_id == product_id
        assert restored.priority == 8

    def test_price_updated_event_json_roundtrip(self):
        product_id = uuid.uuid4()
        original = PriceUpdatedEvent(
            event_id="price-123",
            asin="B08ABC1234",
            product_id=product_id,
            price_full=599.99,
            price_discount=499.99,
            is_out_of_stock=False,
        )
        json_str = original.model_dump_json()
        restored = PriceUpdatedEvent.model_validate_json(json_str)
        assert restored.price_full == 599.99
        assert restored.price_discount == 499.99
        assert restored.is_out_of_stock is False

    def test_alert_triggered_event_json_roundtrip(self):
        user_id = uuid.uuid4()
        product_id = uuid.uuid4()
        original = AlertTriggeredEvent(
            event_id="alert-123",
            alert_type=AlertType.TARGET_PRICE,
            user_id=user_id,
            telegram_chat_id="123456",
            product_id=product_id,
            asin="B08ABC1234",
            title="Test Product",
            current_price=299.99,
            target_price=350.00,
            message="Price dropped!",
        )
        json_str = original.model_dump_json()
        restored = AlertTriggeredEvent.model_validate_json(json_str)
        assert restored.user_id == user_id
        assert restored.alert_type == AlertType.TARGET_PRICE
        assert restored.current_price == 299.99

    def test_user_blocked_event_json_roundtrip(self):
        user_id = uuid.uuid4()
        original = UserBlockedEvent(
            event_id="blocked-123",
            user_id=user_id,
            telegram_chat_id="123456",
            reason="bot_blocked",
        )
        json_str = original.model_dump_json()
        restored = UserBlockedEvent.model_validate_json(json_str)
        assert restored.user_id == user_id
        assert restored.reason == "bot_blocked"

    def test_hard_delete_command_json_roundtrip(self):
        user_id = uuid.uuid4()
        original = HardDeleteCommand(
            event_id="delete-123",
            user_id=user_id,
            telegram_chat_id="123456",
            initiated_by="telegram_403",
        )
        json_str = original.model_dump_json()
        restored = HardDeleteCommand.model_validate_json(json_str)
        assert restored.user_id == user_id
        assert restored.initiated_by == "telegram_403"


class TestUUIDPreservation:
    def test_uuid_format_preserved(self):
        original_uuid = "123e4567-e89b-12d3-a456-426614174000"
        header = MessageHeader(trace_id=original_uuid)
        json_str = header.model_dump_json()
        restored = MessageHeader.model_validate_json(json_str)
        assert str(restored.trace_id) == original_uuid

    def test_uuid_without_hyphens(self):
        original_uuid = "123e4567e89b12d3a456426614174000"
        header = MessageHeader(trace_id=original_uuid)
        json_str = header.model_dump_json()
        restored = MessageHeader.model_validate_json(json_str)
        assert str(restored.trace_id) == "123e4567-e89b-12d3-a456-426614174000"


class TestDatetimePreservation:
    def test_datetime_preserved_through_serialization(self):
        original_dt = datetime(2026, 9, 6, 10, 30, 0)
        header = MessageHeader(timestamp=original_dt)
        json_str = header.model_dump_json()
        restored = MessageHeader.model_validate_json(json_str)
        assert restored.timestamp == original_dt
