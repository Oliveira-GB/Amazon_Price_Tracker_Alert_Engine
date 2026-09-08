import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class TestHandleCommandIntegration:
    @pytest.mark.asyncio
    async def test_start_command_flow(self):
        from api.routes.webhook import handle_command

        mock_bot = AsyncMock()
        sent_text = None

        async def capture_send(chat_id, text, **kwargs):
            nonlocal sent_text
            sent_text = text

        mock_bot.send_message = capture_send

        with patch("api.bot.handlers.get_or_create_user", new_callable=AsyncMock) as mock_get_user:
            mock_user = MagicMock()
            mock_user.quota_limit = 50
            mock_get_user.return_value = mock_user

            await handle_command("chat123", "/start", uuid.uuid4(), mock_bot)

        assert sent_text is not None
        assert "Bem-vindo" in sent_text or "Amazon" in sent_text

    @pytest.mark.asyncio
    async def test_help_command_flow(self):
        from api.routes.webhook import handle_command

        mock_bot = AsyncMock()
        sent_text = None

        async def capture_send(chat_id, text, **kwargs):
            nonlocal sent_text
            sent_text = text

        mock_bot.send_message = capture_send

        await handle_command("chat123", "/help", uuid.uuid4(), mock_bot)

        assert sent_text is not None
        assert "Comandos" in sent_text or "/start" in sent_text

    @pytest.mark.asyncio
    async def test_list_command_flow(self):
        from api.routes.webhook import handle_command

        mock_bot = AsyncMock()
        mock_bot.send_message = AsyncMock()

        with patch("api.bot.handlers.get_or_create_user", new_callable=AsyncMock) as mock_get_user:
            mock_user = MagicMock()
            mock_user.quota_limit = 50
            mock_get_user.return_value = mock_user

            with patch("api.bot.handlers.get_user_subscriptions", new_callable=AsyncMock) as mock_subs:
                mock_subs.return_value = []

                await handle_command("chat123", "/list", uuid.uuid4(), mock_bot)

                mock_bot.send_message.assert_called_once()

    @pytest.mark.asyncio
    async def test_pause_command_without_index(self):
        from api.routes.webhook import handle_command

        mock_bot = AsyncMock()
        sent_text = None

        async def capture_send(chat_id, text, **kwargs):
            nonlocal sent_text
            sent_text = text

        mock_bot.send_message = capture_send

        with patch("api.bot.handlers.get_or_create_user", new_callable=AsyncMock):
            await handle_command("chat123", "/pause", uuid.uuid4(), mock_bot)

        assert sent_text is not None
        assert "/list" in sent_text

    @pytest.mark.asyncio
    async def test_request_upgrade_command_flow(self):
        from api.routes.webhook import handle_command

        mock_bot = AsyncMock()
        mock_bot.send_message = AsyncMock()

        with patch("api.bot.handlers.get_or_create_user", new_callable=AsyncMock) as mock_get_user:
            mock_user = MagicMock()
            mock_user.quota_limit = 50
            mock_get_user.return_value = mock_user

            with patch("api.bot.handlers.get_user_subscription_count", new_callable=AsyncMock) as mock_count:
                mock_count.return_value = 45

                await handle_command("chat123", "/request_upgrade", uuid.uuid4(), mock_bot)

                assert mock_bot.send_message.call_count == 2

    @pytest.mark.asyncio
    async def test_unknown_command_flow(self):
        from api.routes.webhook import handle_command

        mock_bot = AsyncMock()
        sent_text = None

        async def capture_send(chat_id, text, **kwargs):
            nonlocal sent_text
            sent_text = text

        mock_bot.send_message = capture_send

        await handle_command("chat123", "/unknown_cmd", uuid.uuid4(), mock_bot)

        assert sent_text is not None
        assert "reconhecido" in sent_text.lower()

    @pytest.mark.asyncio
    async def test_command_case_insensitive(self):
        from api.routes.webhook import handle_command

        mock_bot = AsyncMock()
        sent_text = None

        async def capture_send(chat_id, text, **kwargs):
            nonlocal sent_text
            sent_text = text

        mock_bot.send_message = capture_send

        with patch("api.bot.handlers.get_or_create_user", new_callable=AsyncMock) as mock_get_user:
            mock_user = MagicMock()
            mock_user.quota_limit = 50
            mock_get_user.return_value = mock_user

            await handle_command("chat123", "/START", uuid.uuid4(), mock_bot)

        assert sent_text is not None
        assert "Bem-vindo" in sent_text or "Amazon" in sent_text

    @pytest.mark.asyncio
    async def test_command_with_extra_args(self):
        from api.routes.webhook import handle_command

        mock_bot = AsyncMock()
        sent_text = None

        async def capture_send(chat_id, text, **kwargs):
            nonlocal sent_text
            sent_text = text

        mock_bot.send_message = capture_send

        with patch("api.bot.handlers.get_or_create_user", new_callable=AsyncMock) as mock_get_user:
            mock_user = MagicMock()
            mock_user.quota_limit = 50
            mock_get_user.return_value = mock_user

            await handle_command("chat123", "/start extra args", uuid.uuid4(), mock_bot)

        assert sent_text is not None
