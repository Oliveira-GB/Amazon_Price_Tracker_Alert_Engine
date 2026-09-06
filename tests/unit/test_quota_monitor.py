import pytest
import respx
from httpx import Response

from core.config import settings
from core.quota_monitor import CloudAMQPQuotaMonitor


class TestCloudAMQPQuotaMonitor:
    @pytest.fixture
    def monitor(self):
        return CloudAMQPQuotaMonitor()

    @pytest.fixture(autouse=True)
    def configured_telegram_credentials(self, monkeypatch):
        monkeypatch.setattr(settings, "TG_BOT_TOKEN", "test_bot_token")
        monkeypatch.setattr(settings, "ADMIN_TELEGRAM_ID", "123456789")

    @respx.mock
    async def test_quota_not_exceeded_allows_publishing(self, monitor):
        overview_url = f"{monitor.management_base_url}/api/vhosts/%2f/overview"
        respx.get(overview_url).mock(
            return_value=Response(
                200,
                json={
                    "messages_ready": 100,
                    "messages_unacknowledged": 50,
                    "message_stats": {"publish": 500_000},
                },
            )
        )

        exceeded = await monitor.check_and_alert()

        assert exceeded is False

    @respx.mock
    async def test_quota_exceeded_blocks_publishing_and_sends_telegram_alert(self, monitor):
        overview_url = f"{monitor.management_base_url}/api/vhosts/%2f/overview"
        respx.get(overview_url).mock(
            return_value=Response(
                200,
                json={
                    "messages_ready": 10_000,
                    "messages_unacknowledged": 5_000,
                    "message_stats": {"publish": 960_000},
                },
            )
        )

        telegram_route = respx.post(
            f"https://api.telegram.org/bot{settings.TG_BOT_TOKEN}/sendMessage"
        ).mock(return_value=Response(200, json={"ok": True}))

        exceeded = await monitor.check_and_alert()

        assert exceeded is True
        assert telegram_route.called
        request_body = telegram_route.calls.last.request.content.decode()
        assert "960,000" in request_body
        assert "123456789" in request_body

    @respx.mock
    async def test_compute_consumed_fallback_without_publish_stats(self, monitor):
        overview_url = f"{monitor.management_base_url}/api/vhosts/%2f/overview"
        respx.get(overview_url).mock(
            return_value=Response(
                200,
                json={
                    "messages_ready": 600_000,
                    "messages_unacknowledged": 350_000,
                },
            )
        )

        exceeded = await monitor.check_and_alert()

        assert exceeded is True

    @respx.mock
    async def test_api_error_does_not_block_publishing(self, monitor):
        overview_url = f"{monitor.management_base_url}/api/vhosts/%2f/overview"
        respx.get(overview_url).mock(return_value=Response(503))

        exceeded = await monitor.check_and_alert()

        assert exceeded is False

    @respx.mock
    async def test_disabled_check_always_allows_publishing(self, monkeypatch):
        monkeypatch.setattr(settings, "QUOTA_CHECK_ENABLED", False)
        monitor = CloudAMQPQuotaMonitor()

        exceeded = await monitor.check_and_alert()

        assert exceeded is False
