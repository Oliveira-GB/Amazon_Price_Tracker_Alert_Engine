from unittest.mock import patch

import pytest
from fastapi import HTTPException

from api.dependencies import verify_telegram_secret


class TestVerifyTelegramSecret:
    def test_valid_secret_in_production(self):
        with patch("core.config.settings") as mock_settings:
            mock_settings.APP_ENV = "production"
            mock_settings.TG_BOT_WEBHOOK_SECRET = "my_webhook_secret"
            result = verify_telegram_secret("my_webhook_secret")
            assert result == "my_webhook_secret"

    def test_invalid_secret_in_production(self):
        with patch("core.config.settings") as mock_settings:
            mock_settings.APP_ENV = "production"
            mock_settings.TG_BOT_WEBHOOK_SECRET = "my_webhook_secret"
            with pytest.raises(HTTPException) as exc_info:
                verify_telegram_secret("wrong_token")
            assert exc_info.value.status_code == 403
            assert "Invalid token" in exc_info.value.detail

    def test_testing_env_always_passes(self):
        with patch("core.config.settings") as mock_settings:
            mock_settings.APP_ENV = "testing"
            mock_settings.TG_BOT_WEBHOOK_SECRET = "my_webhook_secret"
            result = verify_telegram_secret("any_token")
            assert result == "dev"

    def test_missing_header_in_production(self):
        with patch("core.config.settings") as mock_settings:
            mock_settings.APP_ENV = "production"
            mock_settings.TG_BOT_WEBHOOK_SECRET = "my_webhook_secret"
            with pytest.raises(HTTPException) as exc_info:
                verify_telegram_secret(None)
            assert exc_info.value.status_code == 403

    def test_development_env_still_validates(self):
        with patch("core.config.settings") as mock_settings:
            mock_settings.APP_ENV = "development"
            mock_settings.TG_BOT_WEBHOOK_SECRET = "my_webhook_secret"
            with pytest.raises(HTTPException) as exc_info:
                verify_telegram_secret("wrong_token")
            assert exc_info.value.status_code == 403
