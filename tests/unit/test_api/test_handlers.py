from unittest.mock import AsyncMock, MagicMock, patch
import uuid

import pytest


class TestHandleStart:
    @pytest.mark.asyncio
    async def test_handle_start_creates_user_and_sends_message(self):
        from api.bot.handlers import handle_start

        mock_bot = AsyncMock()
        mock_bot.send_message = AsyncMock()

        with patch("api.bot.handlers.async_session_factory") as mock_session_factory:
            mock_session = AsyncMock()
            mock_session_factory.return_value.__aenter__.return_value = mock_session
            mock_session.commit = AsyncMock()

            with patch("api.bot.handlers.get_or_create_user", new_callable=AsyncMock) as mock_get_user:
                mock_user = MagicMock()
                mock_user.quota_limit = 50
                mock_get_user.return_value = mock_user

                await handle_start(mock_bot, "chat123", uuid.uuid4())

                mock_bot.send_message.assert_called_once()
                call_args = mock_bot.send_message.call_args
                assert "chat123" in call_args[0]


class TestHandleHelp:
    @pytest.mark.asyncio
    async def test_handle_help_sends_help_message(self):
        from api.bot.handlers import handle_help

        mock_bot = AsyncMock()
        mock_bot.send_message = AsyncMock()

        await handle_help(mock_bot, "chat123", uuid.uuid4())

        mock_bot.send_message.assert_called_once()


class TestHandleList:
    @pytest.mark.asyncio
    async def test_handle_list_empty(self):
        from api.bot.handlers import handle_list

        mock_bot = AsyncMock()
        mock_bot.send_message = AsyncMock()

        with patch("api.bot.handlers.async_session_factory") as mock_session_factory:
            mock_session = AsyncMock()
            mock_session_factory.return_value.__aenter__.return_value = mock_session

            with patch("api.bot.handlers.get_or_create_user", new_callable=AsyncMock) as mock_get_user:
                mock_user = MagicMock()
                mock_user.quota_limit = 50
                mock_get_user.return_value = mock_user

                with patch("api.bot.handlers.get_user_subscriptions", new_callable=AsyncMock) as mock_get_subs:
                    mock_get_subs.return_value = []

                    await handle_list(mock_bot, "chat123", uuid.uuid4())

                    mock_bot.send_message.assert_called_once()


class TestHandlePause:
    @pytest.mark.asyncio
    async def test_handle_pause_without_index(self):
        from api.bot.handlers import handle_pause

        mock_bot = AsyncMock()
        mock_bot.send_message = AsyncMock()

        with patch("api.bot.handlers.async_session_factory") as mock_session_factory:
            mock_session = AsyncMock()
            mock_session_factory.return_value.__aenter__.return_value = mock_session

            with patch("api.bot.handlers.get_or_create_user", new_callable=AsyncMock):
                await handle_pause(mock_bot, "chat123", uuid.uuid4(), None)

                mock_bot.send_message.assert_called_once()
                call_args = mock_bot.send_message.call_args
                assert "/list" in call_args[0][1]


class TestHandleDelete:
    @pytest.mark.asyncio
    async def test_handle_delete_without_index(self):
        from api.bot.handlers import handle_delete

        mock_bot = AsyncMock()
        mock_bot.send_message = AsyncMock()

        with patch("api.bot.handlers.async_session_factory") as mock_session_factory:
            mock_session = AsyncMock()
            mock_session_factory.return_value.__aenter__.return_value = mock_session

            with patch("api.bot.handlers.get_or_create_user", new_callable=AsyncMock):
                await handle_delete(mock_bot, "chat123", uuid.uuid4(), None)

                mock_bot.send_message.assert_called_once()
                call_args = mock_bot.send_message.call_args
                assert "/list" in call_args[0][1]


class TestHandleRequestUpgrade:
    @pytest.mark.asyncio
    async def test_handle_request_upgrade_notifies_admin(self):
        from api.bot.handlers import handle_request_upgrade
        from core.config import settings

        mock_bot = AsyncMock()
        mock_bot.send_message = AsyncMock()

        with patch("api.bot.handlers.async_session_factory") as mock_session_factory:
            mock_session = AsyncMock()
            mock_session_factory.return_value.__aenter__.return_value = mock_session

            with patch("api.bot.handlers.get_or_create_user", new_callable=AsyncMock) as mock_get_user:
                mock_user = MagicMock()
                mock_user.quota_limit = 50
                mock_get_user.return_value = mock_user

                with patch("api.bot.handlers.get_user_subscription_count", new_callable=AsyncMock) as mock_count:
                    mock_count.return_value = 45

                    with patch.object(settings, "ADMIN_TELEGRAM_ID", "admin_chat_123"):
                        await handle_request_upgrade(mock_bot, "chat123", uuid.uuid4())

                        assert mock_bot.send_message.call_count == 2


class TestExtractPriceFromText:
    def test_extract_price_in_text_message(self):
        from core.utils import extract_price_from_text

        result = extract_price_from_text("Preço: 299.90")
        assert result == 299.90

    def test_extract_price_no_price_in_url(self):
        from core.utils import extract_price_from_text

        result = extract_price_from_text("https://amazon.com.br/dp/B08ABC1234")
        assert result is None


class TestGetOrCreateUser:
    @pytest.mark.asyncio
    async def test_get_or_create_user_existing(self):
        from api.bot.handlers import get_or_create_user

        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_user = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_user
        mock_session.execute.return_value = mock_result

        result = await get_or_create_user(mock_session, "chat123")

        assert result == mock_user
        assert mock_user.last_seen_at is not None

    @pytest.mark.asyncio
    async def test_get_or_create_user_new(self):
        from api.bot.handlers import get_or_create_user
        from core.config import settings

        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result
        mock_session.add = MagicMock()
        mock_session.flush = AsyncMock()

        with patch.object(settings, "MAX_USER_QUOTA", 50):
            result = await get_or_create_user(mock_session, "chat123")

            mock_session.add.assert_called_once()


class TestGetUserSubscriptionCount:
    @pytest.mark.asyncio
    async def test_get_user_subscription_count(self):
        from api.bot.handlers import get_user_subscription_count
        import uuid

        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar.return_value = 5
        mock_session.execute.return_value = mock_result

        user_id = uuid.uuid4()
        result = await get_user_subscription_count(mock_session, user_id)

        assert result == 5
