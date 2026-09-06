import uuid
from unittest.mock import AsyncMock, patch

import pytest


class TestHandleCommand:
    @pytest.mark.asyncio
    async def test_start_command(self):
        from api.routes.webhook import handle_command

        chat_id = "123456"
        trace_id = uuid.uuid4()
        sent_message = None

        async def capture_message(cid, msg, tid):
            nonlocal sent_message
            sent_message = msg

        with patch("api.routes.webhook.send_text_message", new=capture_message):
            await handle_command(chat_id, "/start", trace_id)

        assert sent_message is not None
        assert "Bem-vindo" in sent_message or "Amazon" in sent_message

    @pytest.mark.asyncio
    async def test_help_command(self):
        from api.routes.webhook import handle_command

        chat_id = "123456"
        trace_id = uuid.uuid4()
        sent_message = None

        async def capture_message(cid, msg, tid):
            nonlocal sent_message
            sent_message = msg

        with patch("api.routes.webhook.send_text_message", new=capture_message):
            await handle_command(chat_id, "/help", trace_id)

        assert sent_message is not None
        assert "Comandos disponíveis" in sent_message or "/start" in sent_message

    @pytest.mark.asyncio
    async def test_list_command(self):
        from api.routes.webhook import handle_command

        chat_id = "123456"
        trace_id = uuid.uuid4()

        with patch("api.routes.webhook.send_list_message", new=AsyncMock()) as mock_list:
            await handle_command(chat_id, "/list", trace_id)
            mock_list.assert_called_once()

    @pytest.mark.asyncio
    async def test_pause_command(self):
        from api.routes.webhook import handle_command

        chat_id = "123456"
        trace_id = uuid.uuid4()
        sent_message = None

        async def capture_message(cid, msg, tid):
            nonlocal sent_message
            sent_message = msg

        with patch("api.routes.webhook.send_text_message", new=capture_message):
            await handle_command(chat_id, "/pause", trace_id)

        assert sent_message is not None
        assert "gerenciar" in sent_message.lower() or "pause" in sent_message.lower()

    @pytest.mark.asyncio
    async def test_request_upgrade_command(self):
        from api.routes.webhook import handle_command

        chat_id = "123456"
        trace_id = uuid.uuid4()
        sent_message = None

        async def capture_message(cid, msg, tid):
            nonlocal sent_message
            sent_message = msg

        with patch("api.routes.webhook.send_text_message", new=capture_message):
            await handle_command(chat_id, "/request_upgrade", trace_id)

        assert sent_message is not None
        assert "limite" in sent_message.lower() or "50" in sent_message

    @pytest.mark.asyncio
    async def test_unknown_command(self):
        from api.routes.webhook import handle_command

        chat_id = "123456"
        trace_id = uuid.uuid4()
        sent_message = None

        async def capture_message(cid, msg, tid):
            nonlocal sent_message
            sent_message = msg

        with patch("api.routes.webhook.send_text_message", new=capture_message):
            await handle_command(chat_id, "/unknown_cmd", trace_id)

        assert sent_message is not None
        assert "não reconhecido" in sent_message.lower()

    @pytest.mark.asyncio
    async def test_command_case_insensitive(self):
        from api.routes.webhook import handle_command

        chat_id = "123456"
        trace_id = uuid.uuid4()
        sent_message = None

        async def capture_message(cid, msg, tid):
            nonlocal sent_message
            sent_message = msg

        with patch("api.routes.webhook.send_text_message", new=capture_message):
            await handle_command(chat_id, "/START", trace_id)

        assert sent_message is not None
        assert "Bem-vindo" in sent_message or "Amazon" in sent_message

    @pytest.mark.asyncio
    async def test_command_with_extra_args(self):
        from api.routes.webhook import handle_command

        chat_id = "123456"
        trace_id = uuid.uuid4()
        sent_message = None

        async def capture_message(cid, msg, tid):
            nonlocal sent_message
            sent_message = msg

        with patch("api.routes.webhook.send_text_message", new=capture_message):
            await handle_command(chat_id, "/start extra args", trace_id)

        assert sent_message is not None
