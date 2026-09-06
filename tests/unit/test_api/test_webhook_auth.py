from unittest.mock import patch

import pytest
from fastapi import HTTPException

from api.dependencies import verify_telegram_secret


class TestVerifyTelegramSecret:
    def test_valid_token(self):
        with patch("core.config.settings") as mock_settings:
            mock_settings.TG_BOT_TOKEN = "my_secret_token"
            result = verify_telegram_secret("my_secret_token")
            assert result == "my_secret_token"

    def test_invalid_token(self):
        with patch("core.config.settings") as mock_settings:
            mock_settings.TG_BOT_TOKEN = "my_secret_token"
            with pytest.raises(HTTPException) as exc_info:
                verify_telegram_secret("wrong_token")
            assert exc_info.value.status_code == 403
            assert "Invalid token" in exc_info.value.detail

    def test_empty_token_config(self):
        with patch("core.config.settings") as mock_settings:
            mock_settings.TG_BOT_TOKEN = ""
            result = verify_telegram_secret("any_token")
            assert result == "dev"

    def test_missing_header(self):
        with patch("core.config.settings") as mock_settings:
            mock_settings.TG_BOT_TOKEN = "my_secret_token"
            with pytest.raises(HTTPException) as exc_info:
                verify_telegram_secret(None)
            assert exc_info.value.status_code == 403

    def test_token_enumeration_prevented(self):
        with patch("core.config.settings") as mock_settings:
            mock_settings.TG_BOT_TOKEN = "correct_token_123"
            with pytest.raises(HTTPException) as exc_info:
                verify_telegram_secret("wrong_token_1")
            assert exc_info.value.status_code == 403
