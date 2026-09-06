import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from aio_pika import IncomingMessage
from bs4 import BeautifulSoup

from workers.validation.consumer import (
    ValidationWorker,
    extract_asins_from_text,
    fetch_title_and_image,
    resolve_url,
)


class TestExtractAsinsFromText:
    def test_extracts_asin_from_clean_url(self):
        text = "https://www.amazon.com.br/dp/B08N5WRWNW"
        asins = extract_asins_from_text(text)
        assert asins == ["B08N5WRWNW"]

    def test_extracts_asin_from_dirty_affiliate_url(self):
        text = "https://www.amazon.com.br/dp/B08N5WRWNW?tag=affiliate-20&ref_=ref"
        asins = extract_asins_from_text(text)
        assert asins == ["B08N5WRWNW"]

    def test_returns_empty_for_non_amazon_url(self):
        text = "https://mercadolivre.com.br/produto/123"
        asins = extract_asins_from_text(text)
        assert asins == []


class TestResolveUrl:
    async def test_follows_redirect(self):
        client = AsyncMock()
        client.head.return_value = MagicMock(url="https://www.amazon.com.br/dp/B08N5WRWNW")

        result = await resolve_url(client, "https://amzn.to/xyz")

        assert result == "https://www.amazon.com.br/dp/B08N5WRWNW"

    async def test_returns_original_url_on_error(self):
        client = AsyncMock()
        client.head.side_effect = Exception("Timeout")

        result = await resolve_url(client, "https://amzn.to/xyz")

        assert result == "https://amzn.to/xyz"


class TestFetchTitleAndImage:
    async def test_extracts_title_and_image(self):
        client = AsyncMock()
        html = """
        <html>
            <input id="productTitle" value="Kindle Paperwhite">
            <img id="landingImage" src="https://image.jpg"/>
        </html>
        """
        client.get.return_value = MagicMock(
            status_code=200,
            text=html,
        )

        title, image = await fetch_title_and_image(client, "B08N5WRWNW")

        assert title == "Kindle Paperwhite"
        assert image == "https://image.jpg"

    async def test_returns_none_on_non_200(self):
        client = AsyncMock()
        client.get.return_value = MagicMock(status_code=503, text="")

        title, image = await fetch_title_and_image(client, "B08N5WRWNW")

        assert title is None
        assert image is None


class TestValidationWorkerProcessMessage:
    @pytest.fixture
    def worker(self, mock_rabbitmq_channel, mock_http_client):
        worker = ValidationWorker()
        worker._channel = mock_rabbitmq_channel
        worker._http_session = mock_http_client
        return worker

    @pytest.fixture
    def sample_command(self, sample_trace_id, sample_timestamp):
        from schemas.commands import ItemValidationCommand

        return ItemValidationCommand(
            event_id="val-123",
            telegram_chat_id="12345",
            raw_url="https://www.amazon.com.br/dp/B08N5WRWNW",
            target_price=200.0,
            alert_on_all_time_low=False,
            trace_id=sample_trace_id,
            timestamp=sample_timestamp,
        )

    @pytest.fixture
    def mock_message(self, sample_command):
        message = AsyncMock(spec=IncomingMessage)
        message.body = sample_command.model_dump_json().encode()
        message.process.return_value.__aenter__ = AsyncMock(return_value=None)
        message.process.return_value.__aexit__ = AsyncMock(return_value=None)
        return message

    async def test_process_message_publishes_success_alert(
        self, worker, mock_message, sample_command, monkeypatch
    ):
        mock_session = AsyncMock()
        mock_result = MagicMock()

        user = MagicMock()
        user.id = uuid.uuid4()
        user.telegram_chat_id = "12345"
        user.last_seen_at = None

        product = MagicMock()
        product.id = uuid.uuid4()
        product.asin = "B08N5WRWNW"
        product.title = "Kindle"
        product.url = "https://www.amazon.com.br/dp/B08N5WRWNW"
        product.image_url = "https://image.jpg"
        product.status = "IDLE"

        # First execute returns user None, second returns product None, third returns subscription None
        mock_result.scalar_one_or_none.side_effect = [None, None, None]
        mock_session.execute.return_value = mock_result
        mock_session.add = MagicMock()
        mock_session.flush = AsyncMock()
        mock_session.commit = AsyncMock()

        with patch("workers.validation.consumer.async_session_factory") as mock_factory:
            mock_factory.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_factory.return_value.__aexit__ = AsyncMock(return_value=None)

            with patch(
                "workers.validation.consumer.fetch_title_and_image",
                return_value=("Kindle", "https://image.jpg"),
            ):
                with patch("workers.validation.consumer.resolve_url") as mock_resolve:
                    mock_resolve.return_value = sample_command.raw_url

                    await worker.process_message(mock_message)

        assert worker._channel.default_exchange.publish.called

    async def test_process_message_invalid_link_publishes_error(
        self, worker, mock_message, sample_trace_id, sample_timestamp
    ):
        from schemas.commands import ItemValidationCommand

        command = ItemValidationCommand(
            event_id="val-123",
            telegram_chat_id="12345",
            raw_url="not-a-valid-url",
            target_price=200.0,
            alert_on_all_time_low=False,
            trace_id=sample_trace_id,
            timestamp=sample_timestamp,
        )
        mock_message.body = command.model_dump_json().encode()

        await worker.process_message(mock_message)

        assert worker._channel.default_exchange.publish.called

    async def test_extract_asins_from_text_handles_short_url(self):
        text = "https://amzn.to/xyz123"
        asins = extract_asins_from_text(text)
        assert asins == []
