import uuid

from schemas.events import AlertTriggeredEvent, AlertType
from workers.notification.consumer import build_telegram_message, escape_markdown


class TestEscapeMarkdown:
    def test_escape_markdown_special_chars(self):
        text = "*_[]()~`>#+\\-=|{}.!"
        escaped = escape_markdown(text)
        assert "\\" in escaped

    def test_escape_markdown_plain_text(self):
        text = "Hello World 123"
        escaped = escape_markdown(text)
        assert escaped == text

    def test_escape_markdown_real_title(self):
        text = "Samsung *Galaxy* S23 [128GB]"
        escaped = escape_markdown(text)
        assert "\\*" in escaped
        assert "\\[" in escaped
        assert "\\]" in escaped

    def test_escape_markdown_nested_brackets(self):
        text = "[Samsung] (_test_) `code`"
        escaped = escape_markdown(text)
        assert escaped.count("\\") >= 4


class TestBuildTelegramMessage:
    def test_build_telegram_message_system(self):
        alert = AlertTriggeredEvent(
            event_id="alert-123",
            alert_type=AlertType.SYSTEM_MESSAGE,
            user_id=uuid.uuid4(),
            telegram_chat_id="123456",
            product_id=uuid.uuid4(),
            asin="B08ABC1234",
            current_price=0.0,
            message="Produto registrado com sucesso!",
        )
        msg = build_telegram_message(alert)
        assert msg["chat_id"] == "123456"
        assert "Produto registrado" in msg["text"]

    def test_build_telegram_message_target_price(self):
        alert = AlertTriggeredEvent(
            event_id="alert-123",
            alert_type=AlertType.TARGET_PRICE,
            user_id=uuid.uuid4(),
            telegram_chat_id="123456",
            product_id=uuid.uuid4(),
            asin="B08ABC1234",
            title="Test Product",
            url="https://amazon.com.br/dp/B08ABC1234",
            current_price=299.99,
            target_price=350.00,
            previous_price=499.99,
            message="Price dropped!",
        )
        msg = build_telegram_message(alert)
        assert msg["chat_id"] == "123456"
        assert "299.99" in msg["text"]
        assert "350.00" in msg["text"]
        assert "markdown" in msg["parse_mode"].lower()

    def test_build_telegram_message_all_time_low(self):
        alert = AlertTriggeredEvent(
            event_id="alert-123",
            alert_type=AlertType.ALL_TIME_LOW,
            user_id=uuid.uuid4(),
            telegram_chat_id="123456",
            product_id=uuid.uuid4(),
            asin="B08ABC1234",
            title="Test Product",
            url="https://amazon.com.br/dp/B08ABC1234",
            current_price=199.99,
            message="New all-time low!",
        )
        msg = build_telegram_message(alert)
        assert "histórico" in msg["text"].lower() or "🏆" in msg["text"]

    def test_build_telegram_message_long_title(self):
        alert = AlertTriggeredEvent(
            event_id="alert-123",
            alert_type=AlertType.TARGET_PRICE,
            user_id=uuid.uuid4(),
            telegram_chat_id="123456",
            product_id=uuid.uuid4(),
            asin="B08ABC1234",
            title="A" * 100,
            current_price=299.99,
            message="Price dropped!",
        )
        msg = build_telegram_message(alert)
        assert msg["text"] is not None
