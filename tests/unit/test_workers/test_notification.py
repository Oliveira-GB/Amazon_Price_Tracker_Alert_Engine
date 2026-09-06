import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from aio_pika import IncomingMessage

from schemas.events import AlertTriggeredEvent, AlertType
from workers.notification.consumer import (
    NotificationWorker,
    build_telegram_message,
    escape_markdown,
)


class TestEscapeMarkdown:
    def test_escapes_special_characters(self):
        assert escape_markdown("Preço *especial*") == "Preço \\*especial\\*"

    def test_no_change_for_plain_text(self):
        assert escape_markdown("Kindle Paperwhite") == "Kindle Paperwhite"


class TestBuildTelegramMessage:
    def test_system_message(self):
        alert = AlertTriggeredEvent(
            event_id="alert-1",
            alert_type=AlertType.SYSTEM_MESSAGE,
            user_id=uuid.uuid4(),
            telegram_chat_id="12345",
            product_id=uuid.uuid4(),
            asin="B08N5WRWNW",
            title="Kindle",
            url="https://amazon.com.br/dp/B08N5WRWNW",
            target_price=None,
            current_price=0.0,
            previous_price=None,
            message="Produto registrado!",
        )
        payload = build_telegram_message(alert)
        assert payload["chat_id"] == "12345"
        assert "Produto registrado" in payload["text"]

    def test_price_alert_message(self):
        alert = AlertTriggeredEvent(
            event_id="alert-1",
            alert_type=AlertType.TARGET_PRICE,
            user_id=uuid.uuid4(),
            telegram_chat_id="12345",
            product_id=uuid.uuid4(),
            asin="B08N5WRWNW",
            title="Kindle",
            url="https://amazon.com.br/dp/B08N5WRWNW",
            target_price=200.0,
            current_price=199.9,
            previous_price=250.0,
            message="",
        )
        payload = build_telegram_message(alert)
        assert "Alerta de Preço" in payload["text"]
        assert "199.90" in payload["text"]


class TestNotificationWorkerProcessNotification:
    @pytest.fixture
    def worker(self, mock_rabbitmq_channel, mock_http_client):
        worker = NotificationWorker("telegram.notification.queue")
        worker._channel = mock_rabbitmq_channel
        worker._http_session = mock_http_client
        return worker

    @pytest.fixture
    def sample_alert(self, sample_trace_id, sample_timestamp):
        return AlertTriggeredEvent(
            event_id="alert-1",
            alert_type=AlertType.TARGET_PRICE,
            user_id=uuid.uuid4(),
            telegram_chat_id="12345",
            product_id=uuid.uuid4(),
            asin="B08N5WRWNW",
            title="Kindle",
            url="https://amazon.com.br/dp/B08N5WRWNW",
            target_price=200.0,
            current_price=199.9,
            previous_price=250.0,
            message="",
            trace_id=sample_trace_id,
            timestamp=sample_timestamp,
        )

    @pytest.fixture
    def mock_message(self, sample_alert):
        message = AsyncMock(spec=IncomingMessage)
        message.body = sample_alert.model_dump_json().encode()
        message.process.return_value.__aenter__ = AsyncMock(return_value=None)
        message.process.return_value.__aexit__ = AsyncMock(return_value=None)
        message.ack = AsyncMock()
        message.nack = AsyncMock()
        return message

    async def test_success_200_acks(self, worker, mock_message, mock_http_client):
        mock_http_client.post.return_value = MagicMock(status_code=200)

        await worker._process_notification(mock_message)

        mock_message.ack.assert_called_once()

    async def test_rate_limit_429_sleeps_and_nacks(self, worker, mock_message, mock_http_client):
        response = MagicMock(status_code=429)
        response.headers = {"Retry-After": "5"}
        mock_http_client.post.return_value = response

        with patch("workers.notification.consumer.asyncio.sleep", new_callable=AsyncMock):
            await worker._process_notification(mock_message)

        mock_message.nack.assert_called_once_with(requeue=True)

    async def test_forbidden_403_publishes_blocked_event(self, worker, mock_message, mock_http_client):
        response = MagicMock(status_code=403)
        mock_http_client.post.return_value = response

        await worker._process_notification(mock_message)

        assert worker._channel.default_exchange.publish.called
        mock_message.ack.assert_called_once()

    async def test_http_error_nacks(self, worker, mock_message, mock_http_client):
        request = MagicMock()
        response = MagicMock(status_code=500)
        response.request = request
        error = httpx.HTTPStatusError("Server error", request=request, response=response)
        mock_http_client.post.side_effect = error

        await worker._process_notification(mock_message)

        mock_message.nack.assert_called_once_with(requeue=True)


class TestNotificationWorkerProcessMaintenance:
    @pytest.fixture
    def worker(self, mock_rabbitmq_channel):
        worker = NotificationWorker("user.maintenance.queue")
        worker._channel = mock_rabbitmq_channel
        return worker

    @pytest.fixture
    def sample_command(self, sample_trace_id, sample_timestamp):
        from schemas.maintenance import HardDeleteCommand

        return HardDeleteCommand(
            event_id="maint-1",
            user_id=uuid.uuid4(),
            telegram_chat_id="12345",
            reason="bot_blocked_by_user",
            initiated_by="notification_worker",
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
        return message

    async def test_hard_delete_user(self, worker, mock_message, sample_command):
        session = AsyncMock()
        user = MagicMock()
        user.id = sample_command.user_id
        user.telegram_chat_id = "12345"

        user_result = MagicMock()
        user_result.scalar_one_or_none.return_value = user

        session.execute.return_value = user_result
        session.commit = AsyncMock()

        with patch("workers.notification.consumer.async_session_factory") as mock_factory:
            mock_factory.return_value.__aenter__ = AsyncMock(return_value=session)
            mock_factory.return_value.__aexit__ = AsyncMock(return_value=None)

            await worker._process_maintenance(mock_message)

        mock_message.ack.assert_called_once()

    async def test_missing_user_acks(self, worker, mock_message, sample_command):
        session = AsyncMock()
        result = MagicMock()
        result.scalar_one_or_none.return_value = None
        session.execute.return_value = result

        with patch("workers.notification.consumer.async_session_factory") as mock_factory:
            mock_factory.return_value.__aenter__ = AsyncMock(return_value=session)
            mock_factory.return_value.__aexit__ = AsyncMock(return_value=None)

            await worker._process_maintenance(mock_message)

        mock_message.ack.assert_called_once()
