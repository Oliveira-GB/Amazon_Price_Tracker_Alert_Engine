import uuid

import pytest
from pydantic import ValidationError

from schemas.events import (
    AlertTriggeredEvent,
    AlertType,
    PriceUpdatedEvent,
)


class TestAlertType:
    def test_alert_type_enum_valid(self):
        assert AlertType.TARGET_PRICE == "target_price"
        assert AlertType.ALL_TIME_LOW == "all_time_low"
        assert AlertType.SYSTEM_MESSAGE == "system_message"

    def test_alert_type_from_string(self):
        assert AlertType("target_price") == AlertType.TARGET_PRICE


class TestPriceUpdatedEvent:
    def test_price_updated_event_all_prices_none(self):
        event = PriceUpdatedEvent(
            event_id="price-123",
            asin="B08ABC1234",
            product_id=uuid.uuid4(),
            price_full=None,
            price_discount=None,
            is_out_of_stock=False,
        )
        assert event.price_full is None
        assert event.price_discount is None

    def test_price_updated_event_with_prices(self):
        event = PriceUpdatedEvent(
            event_id="price-123",
            asin="B08ABC1234",
            product_id=uuid.uuid4(),
            price_full=599.99,
            price_discount=499.99,
        )
        assert event.price_full == 599.99
        assert event.price_discount == 499.99

    def test_price_updated_event_negative_price(self):
        with pytest.raises(ValidationError) as exc_info:
            PriceUpdatedEvent(
                event_id="price-123",
                asin="B08ABC1234",
                product_id=uuid.uuid4(),
                price_full=-10.0,
            )
        assert "price_full" in str(exc_info.value)

    def test_price_updated_event_discount_higher(self):
        event = PriceUpdatedEvent(
            event_id="price-123",
            asin="B08ABC1234",
            product_id=uuid.uuid4(),
            price_full=100.0,
            price_discount=150.0,
        )
        assert event.price_discount > event.price_full

    def test_price_updated_event_out_of_stock(self):
        event = PriceUpdatedEvent(
            event_id="price-123",
            asin="B08ABC1234",
            product_id=uuid.uuid4(),
            price_full=None,
            price_discount=None,
            is_out_of_stock=True,
        )
        assert event.is_out_of_stock is True

    def test_price_updated_event_previous_prices(self):
        event = PriceUpdatedEvent(
            event_id="price-123",
            asin="B08ABC1234",
            product_id=uuid.uuid4(),
            price_full=499.99,
            price_discount=399.99,
            previous_price_full=599.99,
            previous_price_discount=499.99,
        )
        assert event.previous_price_full == 599.99
        assert event.previous_price_discount == 499.99

    def test_price_updated_event_serialization(self):
        product_id = uuid.uuid4()
        event = PriceUpdatedEvent(
            event_id="price-123",
            asin="B08ABC1234",
            product_id=product_id,
            price_full=499.99,
            price_discount=399.99,
        )
        json_data = event.model_dump_json()
        restored = PriceUpdatedEvent.model_validate_json(json_data)
        assert restored.event_id == event.event_id
        assert restored.price_full == event.price_full


class TestAlertTriggeredEvent:
    def test_alert_triggered_event_target_price(self):
        event = AlertTriggeredEvent(
            event_id="alert-123",
            alert_type=AlertType.TARGET_PRICE,
            user_id=uuid.uuid4(),
            telegram_chat_id="123456",
            product_id=uuid.uuid4(),
            asin="B08ABC1234",
            current_price=299.99,
            target_price=350.00,
            message="Price dropped!",
        )
        assert event.alert_type == AlertType.TARGET_PRICE
        assert event.current_price == 299.99

    def test_alert_triggered_event_title_max_length(self):
        event = AlertTriggeredEvent(
            event_id="alert-123",
            alert_type=AlertType.TARGET_PRICE,
            user_id=uuid.uuid4(),
            telegram_chat_id="123456",
            product_id=uuid.uuid4(),
            asin="B08ABC1234",
            current_price=299.99,
            message="Price dropped!",
            title="x" * 200,
        )
        assert len(event.title) == 200

    def test_alert_triggered_event_title_exceeds_max(self):
        with pytest.raises(ValidationError) as exc_info:
            AlertTriggeredEvent(
                event_id="alert-123",
                alert_type=AlertType.TARGET_PRICE,
                user_id=uuid.uuid4(),
                telegram_chat_id="123456",
                product_id=uuid.uuid4(),
                asin="B08ABC1234",
                current_price=299.99,
                message="Price dropped!",
                title="x" * 201,
            )
        assert "title" in str(exc_info.value)

    def test_alert_triggered_event_message_max_length(self):
        event = AlertTriggeredEvent(
            event_id="alert-123",
            alert_type=AlertType.TARGET_PRICE,
            user_id=uuid.uuid4(),
            telegram_chat_id="123456",
            product_id=uuid.uuid4(),
            asin="B08ABC1234",
            current_price=299.99,
            message="x" * 1000,
        )
        assert len(event.message) == 1000

    def test_alert_triggered_event_message_exceeds_max(self):
        with pytest.raises(ValidationError) as exc_info:
            AlertTriggeredEvent(
                event_id="alert-123",
                alert_type=AlertType.TARGET_PRICE,
                user_id=uuid.uuid4(),
                telegram_chat_id="123456",
                product_id=uuid.uuid4(),
                asin="B08ABC1234",
                current_price=299.99,
                message="x" * 1001,
            )
        assert "message" in str(exc_info.value)

    def test_alert_triggered_event_current_price_zero(self):
        event = AlertTriggeredEvent(
            event_id="alert-123",
            alert_type=AlertType.TARGET_PRICE,
            user_id=uuid.uuid4(),
            telegram_chat_id="123456",
            product_id=uuid.uuid4(),
            asin="B08ABC1234",
            current_price=0.0,
            message="Free item!",
        )
        assert event.current_price == 0.0

    def test_alert_triggered_event_all_optional_none(self):
        event = AlertTriggeredEvent(
            event_id="alert-123",
            alert_type=AlertType.SYSTEM_MESSAGE,
            user_id=uuid.uuid4(),
            telegram_chat_id="123456",
            product_id=uuid.uuid4(),
            asin="B08ABC1234",
            current_price=0.0,
            message="Test",
            title=None,
            image_url=None,
            url=None,
            target_price=None,
            previous_price=None,
        )
        assert event.title is None
        assert event.image_url is None
        assert event.url is None

    def test_alert_triggered_event_all_time_low(self):
        event = AlertTriggeredEvent(
            event_id="alert-123",
            alert_type=AlertType.ALL_TIME_LOW,
            user_id=uuid.uuid4(),
            telegram_chat_id="123456",
            product_id=uuid.uuid4(),
            asin="B08ABC1234",
            current_price=199.99,
            message="New all-time low!",
        )
        assert event.alert_type == AlertType.ALL_TIME_LOW

    def test_alert_triggered_event_serialization(self):
        user_id = uuid.uuid4()
        event = AlertTriggeredEvent(
            event_id="alert-123",
            alert_type=AlertType.TARGET_PRICE,
            user_id=user_id,
            telegram_chat_id="123456",
            product_id=uuid.uuid4(),
            asin="B08ABC1234",
            current_price=299.99,
            target_price=350.00,
            message="Price dropped!",
        )
        json_data = event.model_dump_json()
        restored = AlertTriggeredEvent.model_validate_json(json_data)
        assert restored.user_id == user_id
        assert restored.current_price == 299.99
