import urllib.parse
from typing import Any

import httpx
import structlog

from core.config import settings

logger = structlog.get_logger().bind(worker="CloudAMQPQuotaMonitor")


class CloudAMQPQuotaMonitor:
    """Monitor CloudAMQP message quota via the RabbitMQ Management API.

    Parses ``RABBITMQ_URI`` to discover the management host and credentials,
    queries the vhost overview endpoint, and decides whether the monthly quota
    has been exceeded. When the threshold is crossed it logs a CRITICAL alert
    and optionally notifies the configured admin via Telegram.
    """

    def __init__(self) -> None:
        self._limit = settings.CLOUDAMQP_QUOTA_LIMIT
        self._threshold = settings.CLOUDAMQP_QUOTA_THRESHOLD
        self._enabled = settings.QUOTA_CHECK_ENABLED
        self._admin_chat_id = settings.ADMIN_TELEGRAM_ID
        self._bot_token = settings.TG_BOT_TOKEN
        self._parsed_uri = urllib.parse.urlparse(settings.RABBITMQ_URI)

    @property
    def management_base_url(self) -> str:
        host = self._parsed_uri.hostname or "localhost"
        return f"https://{host}"

    @property
    def management_auth(self) -> tuple[str, str]:
        username = self._parsed_uri.username or "guest"
        password = self._parsed_uri.password or "guest"
        return (username, password)

    @property
    def vhost_name(self) -> str:
        vhost = self._parsed_uri.path or "/"
        vhost = vhost.lstrip("/")
        return vhost or "/"

    def _overview_url(self) -> str:
        vhost = self.vhost_name
        if vhost == "/":
            vhost = "%2f"
        return f"{self.management_base_url}/api/vhosts/{vhost}/overview"

    def _compute_consumed(self, payload: dict[str, Any]) -> int:
        message_stats = payload.get("message_stats") or {}
        published = message_stats.get("publish")
        if published is not None:
            return int(published)

        ready = payload.get("messages_ready", 0) or 0
        unacknowledged = payload.get("messages_unacknowledged", 0) or 0
        return int(ready) + int(unacknowledged)

    async def _fetch_overview(self, client: httpx.AsyncClient) -> dict[str, Any]:
        response = await client.get(
            self._overview_url(),
            auth=self.management_auth,
            timeout=10.0,
        )
        response.raise_for_status()
        return response.json()

    async def _send_admin_alert(self, consumed: int, ratio: float) -> None:
        if not self._admin_chat_id or not self._bot_token:
            return

        text = (
            f"⚠️ *Quota Crítica CloudAMQP*\n\n"
            f"Consumo mensal atingiu *{ratio:.1%}* do limite.\n"
            f"Mensagens: {consumed:,} / {self._limit:,}\n\n"
            f"O Scheduler foi interrompido para evitar cobranças."
        )

        try:
            async with httpx.AsyncClient() as telegram_client:
                await telegram_client.post(
                    f"https://api.telegram.org/bot{self._bot_token}/sendMessage",
                    json={
                        "chat_id": self._admin_chat_id,
                        "text": text,
                        "parse_mode": "Markdown",
                    },
                    timeout=10.0,
                )
        except Exception as e:
            logger.error(
                "failed_to_send_quota_telegram_alert",
                error=str(e),
            )

    async def check_and_alert(self) -> bool:
        """Return ``True`` when the quota threshold is exceeded and publishing should stop."""
        if not self._enabled:
            return False

        try:
            async with httpx.AsyncClient() as client:
                overview = await self._fetch_overview(client)
        except Exception as e:
            logger.error(
                "quota_monitor_api_request_failed",
                error=str(e),
            )
            return False

        consumed = self._compute_consumed(overview)
        ratio = consumed / self._limit if self._limit else 0.0

        logger.info(
            "quota_status_checked",
            consumed=consumed,
            limit=self._limit,
            ratio=ratio,
        )

        if ratio >= self._threshold:
            logger.critical(
                "cloudamqp_quota_exceeded",
                consumed=consumed,
                limit=self._limit,
                ratio=ratio,
                threshold=self._threshold,
            )
            await self._send_admin_alert(consumed, ratio)
            return True

        return False
