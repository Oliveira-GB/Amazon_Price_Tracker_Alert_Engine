import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from aio_pika import IncomingMessage

from workers.decision.consumer import DecisionWorker


class TestDecisionWorkerBuildMessage:
    def test_build_message_with_target(self):
        worker = DecisionWorker()
        message = worker._build_message("B08N5WRWNW", 199.9, 200.0, "Kindle Paperwhite")
        assert "199.90" in message
        assert "200.00" in message
        assert "Kindle" in message

    def test_build_message_all_time_low(self):
        worker = DecisionWorker()
        message = worker._build_message("B08N5WRWNW", 199.9, None, "Kindle")
        assert "histórico" in message
        assert "199.90" in message


class TestDecisionWorkerProcessPriceChange:
    @pytest.fixture
    def worker(self, mock_rabbitmq_channel, mock_redis):
        worker = DecisionWorker()
        worker._channel = mock_rabbitmq_channel
        return worker

    @pytest.fixture
    def sample_event(self, sample_trace_id, sample_timestamp):
        from schemas.events import PriceUpdatedEvent

        return PriceUpdatedEvent(
            event_id="price-123",
            asin="B08N5WRWNW",
            product_id=uuid.uuid4(),
            price_full=299.9,
            price_discount=199.9,
            is_out_of_stock=False,
            previous_price_full=299.9,
            previous_price_discount=249.9,
            trace_id=sample_trace_id,
            timestamp=sample_timestamp,
        )

    async def test_triggers_alert_when_target_met(
        self, worker, sample_event, mock_redis, monkeypatch
    ):
        monkeypatch.setattr("workers.decision.consumer.get_redis", AsyncMock(return_value=mock_redis))

        session = AsyncMock()
        product = MagicMock()
        product.id = sample_event.product_id
        product.title = "Kindle"
        product.all_time_low = 180.0
        product.url = "https://amazon.com.br/dp/B08N5WRWNW"
        product.image_url = "https://image.jpg"

        subscription = MagicMock()
        subscription.user_id = uuid.uuid4()
        subscription.product_id = sample_event.product_id
        subscription.target_price = 200.0
        subscription.alert_on_all_time_low = False
        subscription.last_notified_at = None
        subscription.is_active = True

        subscriptions_result = MagicMock()
        subscriptions_result.scalars.return_value.all.return_value = [subscription]

        product_result = MagicMock()
        product_result.scalar_one_or_none.return_value = product

        session.execute.return_value = subscriptions_result
        session.commit = AsyncMock()

        await worker._process_price_change(session, sample_event, product)

        assert worker._channel.default_exchange.publish.called

    async def test_respects_redis_cooldown(self, worker, sample_event, monkeypatch):
        redis = AsyncMock()
        redis.exists = AsyncMock(return_value=True)
        monkeypatch.setattr("workers.decision.consumer.get_redis", AsyncMock(return_value=redis))

        session = AsyncMock()
        product = MagicMock()
        product.id = sample_event.product_id
        product.title = "Kindle"
        product.all_time_low = 180.0

        subscription = MagicMock()
        subscription.user_id = uuid.uuid4()
        subscription.target_price = 200.0
        subscription.alert_on_all_time_low = False
        subscription.last_notified_at = None
        subscription.is_active = True

        subscriptions_result = MagicMock()
        subscriptions_result.scalars.return_value.all.return_value = [subscription]

        product_result = MagicMock()
        product_result.scalar_one_or_none.return_value = product

        session.execute.side_effect = [product_result, subscriptions_result]

        await worker._process_price_change(session, sample_event, product)

        assert not worker._channel.default_exchange.publish.called

    async def test_redis_fallback_uses_last_notified_at(self, worker, sample_event, monkeypatch):
        redis = AsyncMock()
        redis.exists = AsyncMock(side_effect=Exception("Connection refused"))
        monkeypatch.setattr("workers.decision.consumer.get_redis", AsyncMock(return_value=redis))

        session = AsyncMock()
        product = MagicMock()
        product.id = sample_event.product_id
        product.title = "Kindle"
        product.all_time_low = 180.0

        subscription = MagicMock()
        subscription.user_id = uuid.uuid4()
        subscription.target_price = 200.0
        subscription.alert_on_all_time_low = False
        subscription.last_notified_at = datetime.now(UTC)
        subscription.is_active = True

        subscriptions_result = MagicMock()
        subscriptions_result.scalars.return_value.all.return_value = [subscription]

        product_result = MagicMock()
        product_result.scalar_one_or_none.return_value = product

        session.execute.side_effect = [product_result, subscriptions_result]

        await worker._process_price_change(session, sample_event, product)

        assert not worker._channel.default_exchange.publish.called


class TestDecisionWorkerProcessMessage:
    @pytest.fixture
    def worker(self, mock_rabbitmq_channel):
        worker = DecisionWorker()
        worker._channel = mock_rabbitmq_channel
        return worker

    @pytest.fixture
    def sample_event(self, sample_trace_id, sample_timestamp):
        from schemas.events import PriceUpdatedEvent

        return PriceUpdatedEvent(
            event_id="price-123",
            asin="B08N5WRWNW",
            product_id=uuid.uuid4(),
            price_full=299.9,
            price_discount=199.9,
            is_out_of_stock=False,
            previous_price_full=299.9,
            previous_price_discount=249.9,
            trace_id=sample_trace_id,
            timestamp=sample_timestamp,
        )

    @pytest.fixture
    def mock_message(self, sample_event):
        message = AsyncMock(spec=IncomingMessage)
        message.body = sample_event.model_dump_json().encode()
        message.process.return_value.__aenter__ = AsyncMock(return_value=None)
        message.process.return_value.__aexit__ = AsyncMock(return_value=None)
        message.ack = AsyncMock()
        message.nack = AsyncMock()
        return message

    async def test_missing_product_returns_without_error(self, worker, mock_message, monkeypatch):
        monkeypatch.setattr("workers.decision.consumer.get_redis", AsyncMock(return_value=AsyncMock()))

        session = AsyncMock()
        result = MagicMock()
        result.scalar_one_or_none.return_value = None
        session.execute.return_value = result

        with patch("workers.decision.consumer.async_session_factory") as mock_factory:
            mock_factory.return_value.__aenter__ = AsyncMock(return_value=session)
            mock_factory.return_value.__aexit__ = AsyncMock(return_value=None)

            await worker.process_message(mock_message)

        # Worker returns without ack/nack when product is missing; message stays in queue for retry
        assert not mock_message.ack.called
        assert not mock_message.nack.called
