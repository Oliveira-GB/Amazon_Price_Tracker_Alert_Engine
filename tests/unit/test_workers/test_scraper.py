import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from aio_pika import IncomingMessage

from workers.scraper.consumer import CircuitBreaker, ScraperWorker, extract_price


class TestExtractPrice:
    def test_extracts_brazilian_price(self):
        assert extract_price("R$ 1.234,56") == 1234.56

    def test_extracts_simple_price(self):
        assert extract_price("R$ 299.90") == 299.9

    def test_returns_none_for_invalid_text(self):
        assert extract_price("Indisponível") is None


class TestCircuitBreaker:
    def test_starts_closed(self):
        cb = CircuitBreaker(threshold=3, timeout=60)
        assert cb.is_open() is False

    def test_opens_after_threshold_failures(self):
        cb = CircuitBreaker(threshold=2, timeout=60)
        cb.record_failure()
        assert cb.is_open() is False
        cb.record_failure()
        assert cb.is_open() is True

    def test_records_success_resets_failures(self):
        cb = CircuitBreaker(threshold=2, timeout=60)
        cb.record_failure()
        cb.record_success()
        assert cb.failures == 0
        assert cb.is_open() is False


class TestScraperWorkerProcessMessage:
    @pytest.fixture
    def worker(self, mock_rabbitmq_channel):
        worker = ScraperWorker()
        worker._channel = mock_rabbitmq_channel
        worker._http_session = AsyncMock()
        return worker

    @pytest.fixture
    def sample_command(self, sample_trace_id, sample_timestamp):
        from schemas.commands import ScrapeCommand

        return ScrapeCommand(
            event_id="scrape-123",
            asin="B08N5WRWNW",
            product_id=uuid.uuid4(),
            priority=5,
            trace_id=sample_trace_id,
            timestamp=sample_timestamp,
        )

    @pytest.fixture
    def mock_message(self, sample_command):
        message = AsyncMock(spec=IncomingMessage)
        message.body = sample_command.model_dump_json().encode()
        message.process.return_value.__aenter__ = AsyncMock(return_value=None)
        message.process.return_value.__aexit__ = AsyncMock(return_value=None)
        message.ack = AsyncMock()
        message.nack = AsyncMock()
        return message

    async def test_price_changed_publishes_event(self, worker, mock_message, sample_command):
        html = """
        <html>
            <span class="a-price"><span class="a-offscreen">R$ 199,90</span></span>
        </html>
        """
        response = MagicMock(status_code=200, text=html)
        response.request = MagicMock()
        worker._http_session.get.return_value = response

        mock_session = AsyncMock()
        product = MagicMock()
        product.id = sample_command.product_id
        product.last_price_full = 299.9
        product.last_price_discount = None
        product.all_time_low = None
        product.status = "ACTIVE"

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = product
        mock_session.execute.return_value = mock_result
        mock_session.add = MagicMock()
        mock_session.commit = AsyncMock()

        with patch("workers.scraper.consumer.async_session_factory") as mock_factory:
            mock_factory.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_factory.return_value.__aexit__ = AsyncMock(return_value=None)

            await worker.process_message(mock_message)

        assert worker._channel.default_exchange.publish.called
        mock_message.ack.assert_called_once()

    async def test_404_marks_unavailable_and_acks(self, worker, mock_message, sample_command):
        request = MagicMock()
        response = MagicMock(status_code=404)
        response.request = request
        error = httpx.HTTPStatusError("Not found", request=request, response=response)
        worker._http_session.get.side_effect = error

        mock_session = AsyncMock()
        product = MagicMock()
        product.id = sample_command.product_id
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = product
        mock_session.execute.return_value = mock_result
        mock_session.commit = AsyncMock()

        with patch("workers.scraper.consumer.async_session_factory") as mock_factory:
            mock_factory.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_factory.return_value.__aexit__ = AsyncMock(return_value=None)

            await worker.process_message(mock_message)

        assert product.status == "UNAVAILABLE"
        mock_message.ack.assert_called_once()

    async def test_503_nacks_for_retry(self, worker, mock_message, sample_command):
        request = MagicMock()
        response = MagicMock(status_code=503)
        response.request = request
        error = httpx.HTTPStatusError("Blocked", request=request, response=response)
        worker._http_session.get.side_effect = error

        with patch("workers.scraper.consumer.async_session_factory") as mock_factory:
            mock_factory.return_value.__aenter__ = AsyncMock(return_value=AsyncMock())
            mock_factory.return_value.__aexit__ = AsyncMock(return_value=None)

            await worker.process_message(mock_message)

        mock_message.nack.assert_called_once_with(requeue=True)

    async def test_circuit_breaker_open_nacks_and_sleeps(self, worker, mock_message):
        worker._circuit_breaker.record_failure()
        worker._circuit_breaker.record_failure()
        worker._circuit_breaker.record_failure()
        worker._circuit_breaker.record_failure()
        worker._circuit_breaker.record_failure()

        with patch("workers.scraper.consumer.asyncio.sleep", new_callable=AsyncMock):
            await worker.process_message(mock_message)

        mock_message.nack.assert_called_once_with(requeue=True)
