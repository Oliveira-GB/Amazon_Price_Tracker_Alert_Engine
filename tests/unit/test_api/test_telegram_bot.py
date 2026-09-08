from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from api.bot.client import CircuitBreakerOpen, TelegramBot, TelegramResponse


class TestTelegramBot:
    def test_init_with_token(self):
        bot = TelegramBot(token="test_token_123")
        assert bot.token == "test_token_123"
        assert "test_token_123" in bot.base_url

    def test_init_without_token_uses_settings(self):
        with patch("api.bot.client.settings") as mock_settings:
            mock_settings.TG_BOT_TOKEN = "settings_token"
            bot = TelegramBot()
            assert bot.token == "settings_token"

    def test_circuit_breaker_initially_closed(self):
        bot = TelegramBot(token="test_token")
        assert bot._circuit_open_until is None
        assert bot._consecutive_failures == 0


class TestTelegramBotSendMessage:
    @pytest.mark.asyncio
    async def test_send_message_success(self):
        bot = TelegramBot(token="test_token")
        bot._request = AsyncMock(
            return_value=TelegramResponse(ok=True, result={"message_id": 123})
        )

        result = await bot.send_message("chat123", "Hello world")

        assert result.ok is True
        assert result.result == {"message_id": 123}
        bot._request.assert_called_once()

    @pytest.mark.asyncio
    async def test_send_message_with_reply_markup(self):
        bot = TelegramBot(token="test_token")
        bot._request = AsyncMock(
            return_value=TelegramResponse(ok=True, result={"message_id": 123})
        )

        keyboard = {"inline_keyboard": [[{"text": "Test", "callback_data": "test"}]]}
        await bot.send_message("chat123", "Hello", reply_markup=keyboard)

        call_args = bot._request.call_args
        method, data = call_args[0]
        assert data["reply_markup"] == keyboard

    @pytest.mark.asyncio
    async def test_send_message_parses_mode(self):
        bot = TelegramBot(token="test_token")
        bot._request = AsyncMock(
            return_value=TelegramResponse(ok=True, result={"message_id": 123})
        )

        await bot.send_message("chat123", "Hello", parse_mode="HTML")

        call_args = bot._request.call_args
        method, data = call_args[0]
        assert data["parse_mode"] == "HTML"


class TestTelegramBotEditMessage:
    @pytest.mark.asyncio
    async def test_edit_message_text_success(self):
        bot = TelegramBot(token="test_token")
        bot._request = AsyncMock(
            return_value=TelegramResponse(ok=True, result={"message_id": 123})
        )

        result = await bot.edit_message_text(
            "chat123", 456, "Updated text"
        )

        assert result.ok is True
        call_args = bot._request.call_args
        method, data = call_args[0]
        assert data["text"] == "Updated text"
        assert data["message_id"] == 456


class TestTelegramBotAnswerCallback:
    @pytest.mark.asyncio
    async def test_answer_callback_query_success(self):
        bot = TelegramBot(token="test_token")
        bot._request = AsyncMock(return_value=TelegramResponse(ok=True, result=True))

        result = await bot.answer_callback_query("callback_id_123", "Alert text")

        assert result.ok is True
        call_args = bot._request.call_args
        method, data = call_args[0]
        assert data["callback_query_id"] == "callback_id_123"
        assert data["text"] == "Alert text"


class TestTelegramBotDeleteMessage:
    @pytest.mark.asyncio
    async def test_delete_message_success(self):
        bot = TelegramBot(token="test_token")
        bot._request = AsyncMock(return_value=TelegramResponse(ok=True, result=True))

        result = await bot.delete_message("chat123", 456)

        assert result.ok is True
        call_args = bot._request.call_args
        method, data = call_args[0]
        assert data["chat_id"] == "chat123"
        assert data["message_id"] == 456


class TestCircuitBreaker:
    @pytest.mark.asyncio
    async def test_circuit_breaker_raises_when_open(self):
        from datetime import timedelta
        from datetime import UTC, datetime

        bot = TelegramBot(token="test_token")
        bot._circuit_open_until = datetime.now(UTC) + timedelta(seconds=60)

        with pytest.raises(CircuitBreakerOpen):
            await bot._request("sendMessage", {})

    @pytest.mark.asyncio
    async def test_circuit_breaker_closes_after_timeout(self):
        from datetime import timedelta
        from datetime import UTC, datetime

        bot = TelegramBot(token="test_token")
        bot._circuit_open_until = datetime.now(UTC) - timedelta(seconds=1)

        with patch.object(bot, "_request") as mock_request:
            mock_request.return_value = TelegramResponse(ok=True, result={})
            result = await bot.send_message("chat123", "test")

        assert result.ok is True


class TestGetTelegramBot:
    def test_get_telegram_bot_returns_singleton(self):
        from api.bot.client import get_telegram_bot

        with patch("api.bot.client._bot", None):
            with patch("api.bot.client.TelegramBot") as mock_bot_class:
                mock_bot_instance = MagicMock()
                mock_bot_class.return_value = mock_bot_instance

                bot1 = get_telegram_bot()
                bot2 = get_telegram_bot()

                assert bot1 is bot2
                mock_bot_class.assert_called_once()
