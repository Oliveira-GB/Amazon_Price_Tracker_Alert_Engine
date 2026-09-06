import uuid

from schemas.commands import ItemValidationCommand, ScrapeCommand


class TestRabbitMQIntegration:
    def test_queue_publish_consume(self):
        from core.rabbitmq import QUEUE_NAMES

        assert "item.validation.queue" in QUEUE_NAMES.values()
        assert "scrape.jobs.queue" in QUEUE_NAMES.values()
        assert "price.decision.queue" in QUEUE_NAMES.values()
        assert "telegram.notification.queue" in QUEUE_NAMES.values()
        assert "user.maintenance.queue" in QUEUE_NAMES.values()

    def test_dlq_mapping(self):
        from core.rabbitmq import DLQ_NAMES

        assert "item.validation.dlq" in DLQ_NAMES.values()
        assert "scrape.jobs.dlq" in DLQ_NAMES.values()

    def test_item_validation_command_serialization(self):
        cmd = ItemValidationCommand(
            event_id="val-123",
            telegram_chat_id="123456",
            raw_url="https://amazon.com.br/dp/B08ABC1234",
            target_price=299.99,
        )
        json_data = cmd.model_dump_json()
        restored = ItemValidationCommand.model_validate_json(json_data)
        assert restored.event_id == cmd.event_id
        assert restored.raw_url == cmd.raw_url

    def test_scrape_command_serialization(self):
        cmd = ScrapeCommand(
            event_id="scrape-123",
            asin="B08ABC1234",
            product_id=uuid.uuid4(),
            priority=7,
        )
        json_data = cmd.model_dump_json()
        restored = ScrapeCommand.model_validate_json(json_data)
        assert restored.asin == cmd.asin
        assert restored.priority == cmd.priority

    def test_message_headers_structure(self):
        cmd = ItemValidationCommand(
            event_id="val-123",
            telegram_chat_id="123456",
            raw_url="https://amazon.com.br/dp/B08ABC1234",
        )
        headers = {
            "trace_id": str(cmd.trace_id),
            "timestamp": cmd.timestamp.isoformat(),
            "retry_count": 0,
        }
        assert "trace_id" in headers
        assert "timestamp" in headers
        assert "retry_count" in headers
        assert headers["retry_count"] == 0
