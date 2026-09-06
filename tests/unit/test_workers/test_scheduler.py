


class TestScheduler:
    def test_queue_names_exist(self):
        from core.rabbitmq import QUEUE_NAMES

        assert "item.validation.queue" in QUEUE_NAMES.values()
        assert "scrape.jobs.queue" in QUEUE_NAMES.values()
        assert "price.decision.queue" in QUEUE_NAMES.values()
        assert "telegram.notification.queue" in QUEUE_NAMES.values()
        assert "user.maintenance.queue" in QUEUE_NAMES.values()

    def test_dlq_names_exist(self):
        from core.rabbitmq import DLQ_NAMES

        assert "item.validation.dlq" in DLQ_NAMES.values()
        assert "scrape.jobs.dlq" in DLQ_NAMES.values()
        assert "price.decision.dlq" in DLQ_NAMES.values()
        assert "telegram.notification.dlq" in DLQ_NAMES.values()
        assert "user.maintenance.dlq" in DLQ_NAMES.values()

    def test_dlq_mapping(self):
        from core.rabbitmq import DLQ_NAMES

        assert "item.validation.dlq" in DLQ_NAMES.values()
        assert "scrape.jobs.dlq" in DLQ_NAMES.values()
