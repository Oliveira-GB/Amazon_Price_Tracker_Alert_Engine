import uuid

import pytest
from pydantic import ValidationError

from schemas.commands import (
    ItemValidationCommand,
    MessageType,
    ScrapeCommand,
)


class TestMessageType:
    def test_message_type_enum_valid(self):
        assert MessageType.ITEM_VALIDATION_COMMAND == "item_validation_command"
        assert MessageType.SCRAPE_COMMAND == "scrape_command"
        assert MessageType.PRICE_UPDATED_EVENT == "price_updated_event"
        assert MessageType.ALERT_TRIGGERED_EVENT == "alert_triggered_event"
        assert MessageType.USER_BLOCKED_EVENT == "user_blocked_event"
        assert MessageType.HARD_DELETE_COMMAND == "hard_delete_command"
        assert MessageType.SYSTEM_MESSAGE == "system_message"

    def test_message_type_from_string(self):
        assert MessageType("item_validation_command") == MessageType.ITEM_VALIDATION_COMMAND


class TestItemValidationCommand:
    def test_item_validation_command_valid(self):
        cmd = ItemValidationCommand(
            event_id="test-123",
            telegram_chat_id="123456",
            raw_url="https://amazon.com.br/dp/B08ABC1234",
        )
        assert cmd.event_id == "test-123"
        assert cmd.telegram_chat_id == "123456"
        assert cmd.target_price is None
        assert cmd.alert_on_all_time_low is False

    def test_item_validation_command_with_target_price(self):
        cmd = ItemValidationCommand(
            event_id="test-123",
            telegram_chat_id="123456",
            raw_url="https://amazon.com.br/dp/B08ABC1234",
            target_price=299.99,
        )
        assert cmd.target_price == 299.99

    def test_item_validation_command_target_price_zero(self):
        cmd = ItemValidationCommand(
            event_id="test-123",
            telegram_chat_id="123456",
            raw_url="https://amazon.com.br/dp/B08ABC1234",
            target_price=0.0,
        )
        assert cmd.target_price == 0.0

    def test_item_validation_command_target_price_negative(self):
        cmd = ItemValidationCommand(
            event_id="test-123",
            telegram_chat_id="123456",
            raw_url="https://amazon.com.br/dp/B08ABC1234",
            target_price=-5.0,
        )
        assert cmd.target_price == -5.0

    def test_item_validation_command_empty_url(self):
        cmd = ItemValidationCommand(
            event_id="test-123",
            telegram_chat_id="123456",
            raw_url="",
        )
        assert cmd.raw_url == ""

    def test_item_validation_command_empty_chat_id(self):
        cmd = ItemValidationCommand(
            event_id="test-123",
            telegram_chat_id="",
            raw_url="https://amazon.com.br/dp/B08ABC1234",
        )
        assert cmd.telegram_chat_id == ""

    def test_item_validation_command_affiliate_url(self):
        cmd = ItemValidationCommand(
            event_id="test-123",
            telegram_chat_id="123456",
            raw_url="https://www.amazon.com.br/dp/B08ABC1234?ref=cm_sw_r_ud_dp_ABC123&linkCode=ll1&tag=name-20",
        )
        assert "B08ABC1234" in cmd.raw_url

    def test_item_validation_command_serialization(self):
        cmd = ItemValidationCommand(
            event_id="test-123",
            telegram_chat_id="123456",
            raw_url="https://amazon.com.br/dp/B08ABC1234",
            target_price=299.99,
        )
        json_data = cmd.model_dump_json()
        restored = ItemValidationCommand.model_validate_json(json_data)
        assert restored.event_id == cmd.event_id
        assert restored.target_price == cmd.target_price


class TestScrapeCommand:
    def test_scrape_command_valid(self):
        cmd = ScrapeCommand(
            event_id="scrape-123",
            asin="B08ABC1234",
            product_id=uuid.uuid4(),
        )
        assert cmd.asin == "B08ABC1234"
        assert cmd.priority == 5

    def test_scrape_command_asin_length_9(self):
        with pytest.raises(ValidationError) as exc_info:
            ScrapeCommand(
                event_id="scrape-123",
                asin="B08ABC123",
                product_id=uuid.uuid4(),
            )
        assert "asin" in str(exc_info.value)

    def test_scrape_command_asin_length_10(self):
        cmd = ScrapeCommand(
            event_id="scrape-123",
            asin="B08ABC1234",
            product_id=uuid.uuid4(),
        )
        assert len(cmd.asin) == 10

    def test_scrape_command_asin_length_11(self):
        with pytest.raises(ValidationError) as exc_info:
            ScrapeCommand(
                event_id="scrape-123",
                asin="B08ABC12345",
                product_id=uuid.uuid4(),
            )
        assert "asin" in str(exc_info.value)

    def test_scrape_command_asin_invalid_chars(self):
        cmd = ScrapeCommand(
            event_id="scrape-123",
            asin="B08ABC123!",
            product_id=uuid.uuid4(),
        )
        assert cmd.asin == "B08ABC123!"

    def test_scrape_command_priority_min(self):
        with pytest.raises(ValidationError) as exc_info:
            ScrapeCommand(
                event_id="scrape-123",
                asin="B08ABC1234",
                product_id=uuid.uuid4(),
                priority=0,
            )
        assert "priority" in str(exc_info.value)

    def test_scrape_command_priority_max(self):
        with pytest.raises(ValidationError) as exc_info:
            ScrapeCommand(
                event_id="scrape-123",
                asin="B08ABC1234",
                product_id=uuid.uuid4(),
                priority=11,
            )
        assert "priority" in str(exc_info.value)

    def test_scrape_command_priority_boundary_low(self):
        cmd = ScrapeCommand(
            event_id="scrape-123",
            asin="B08ABC1234",
            product_id=uuid.uuid4(),
            priority=1,
        )
        assert cmd.priority == 1

    def test_scrape_command_priority_boundary_high(self):
        cmd = ScrapeCommand(
            event_id="scrape-123",
            asin="B08ABC1234",
            product_id=uuid.uuid4(),
            priority=10,
        )
        assert cmd.priority == 10

    def test_scrape_command_invalid_uuid(self):
        with pytest.raises(ValidationError) as exc_info:
            ScrapeCommand(
                event_id="scrape-123",
                asin="B08ABC1234",
                product_id="not-a-uuid",
            )
        assert "product_id" in str(exc_info.value)

    def test_scrape_command_serialization(self):
        product_id = uuid.uuid4()
        cmd = ScrapeCommand(
            event_id="scrape-123",
            asin="B08ABC1234",
            product_id=product_id,
            priority=7,
        )
        json_data = cmd.model_dump_json()
        restored = ScrapeCommand.model_validate_json(json_data)
        assert restored.asin == cmd.asin
        assert restored.product_id == product_id
