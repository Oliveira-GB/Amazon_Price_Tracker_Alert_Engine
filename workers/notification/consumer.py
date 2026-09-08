import asyncio
import re
import signal
import uuid
from datetime import UTC, datetime
from typing import Any

import aio_pika
import httpx
from aio_pika import IncomingMessage, Message
from sqlalchemy import delete, select

from core.config import settings
from core.database import async_session_factory
from core.logging import configure_logging
from core.rabbitmq import QUEUE_NAMES
from models.product import Product
from models.user import User
from models.user_product import UserProduct
from schemas.events import AlertTriggeredEvent
from schemas.maintenance import HardDeleteCommand, UserBlockedEvent
from workers.base import BaseWorker

logger: Any = None

TELEGRAM_API_URL = "https://api.telegram.org/bot{bot_token}/sendMessage"

MARKDOWN_ESCAPE_PATTERN = re.compile(r"[*_[\]()~`>#+\-=|{}.!\\]")


def escape_markdown(text: str) -> str:
    return MARKDOWN_ESCAPE_PATTERN.sub(lambda m: "\\" + m.group(), text)


def build_telegram_message(alert: AlertTriggeredEvent) -> dict[str, Any]:
    title = escape_markdown(alert.title) if alert.title else alert.asin

    if alert.alert_type.value == "system_message":
        text = f"ℹ️ {escape_markdown(alert.message)}"
    elif alert.alert_type.value == "all_time_low":
        text = (
            f"🏆 *Preço Histórico!* [{title}]({alert.url})\n\n"
            f"💰 Preço atual: *R$ {alert.current_price:.2f}*\n"
            f"📈 Menor preço já registrado!\n\n"
            f"🔗 https://amazon.com.br/dp/{alert.asin}"
        )
    else:
        text = (
            f"📉 *Alerta de Preço!* [{title}]({alert.url})\n\n"
            f"💰 Preço atual: *R$ {alert.current_price:.2f}*\n"
        )
        if alert.target_price:
            text += f"🎯 Alvo: R$ {alert.target_price:.2f}\n"
        if alert.previous_price:
            drop = alert.previous_price - alert.current_price
            pct = (drop / alert.previous_price) * 100
            text += f"📉 Queda de R$ {drop:.2f} ({pct:.1f}%)\n"
        text += f"\n🔗 https://amazon.com.br/dp/{alert.asin}"

    return {
        "chat_id": alert.telegram_chat_id,
        "text": text,
        "parse_mode": "Markdown",
        "disable_web_page_preview": False,
    }


class NotificationWorker(BaseWorker):
    def __init__(self, queue_name: str) -> None:
        super().__init__("NotificationWorker", queue_name)
        self._http_session: httpx.AsyncClient | None = None

    async def connect(self) -> None:
        await super().connect()
        self._http_session = httpx.AsyncClient()

    async def disconnect(self) -> None:
        if self._http_session:
            await self._http_session.aclose()
            self._http_session = None
        await super().disconnect()

    async def process_message(self, message: IncomingMessage) -> None:
        async with message.process(requeue=False):
            if self.queue_name == QUEUE_NAMES["telegram_notification"]:
                await self._process_notification(message)
            elif self.queue_name == QUEUE_NAMES["user_maintenance"]:
                await self._process_maintenance(message)

    async def _process_notification(self, message: IncomingMessage) -> None:
        alert = AlertTriggeredEvent.model_validate_json(message.body)

        logger.info(
            "notification_started",
            trace_id=str(alert.trace_id),
            event_id=alert.event_id,
            telegram_chat_id=alert.telegram_chat_id,
            alert_type=alert.alert_type.value,
        )

        if not alert.telegram_chat_id:
            async with async_session_factory() as session:
                result = await session.execute(
                    select(User).where(User.id == alert.user_id)
                )
                user = result.scalar_one_or_none()
                if user:
                    alert.telegram_chat_id = user.telegram_chat_id
                else:
                    logger.warning("user_not_found", user_id=str(alert.user_id))
                    return

        try:
            if self._http_session is None:
                raise RuntimeError("HTTP session not initialized")
            response = await self._http_session.post(
                TELEGRAM_API_URL.format(bot_token=settings.TG_BOT_TOKEN),
                json=build_telegram_message(alert),
                timeout=settings.SCRAPE_TIMEOUT_SECONDS,
            )

            if response.status_code == 200:
                logger.info(
                    "notification_sent",
                    event_id=alert.event_id,
                    telegram_chat_id=alert.telegram_chat_id,
                )
                await message.ack()

            elif response.status_code == 429:
                retry_after = int(response.headers.get("Retry-After", 60))
                logger.warning(
                    "telegram_rate_limited",
                    retry_after=retry_after,
                )
                await asyncio.sleep(retry_after)
                await message.nack(requeue=True)

            elif response.status_code == 403:
                logger.warning(
                    "telegram_forbidden",
                    telegram_chat_id=alert.telegram_chat_id,
                )
                if self._channel:
                    blocked_event = UserBlockedEvent(
                        event_id=f"blocked-{uuid.uuid4().hex[:8]}",
                        user_id=alert.user_id,
                        telegram_chat_id=alert.telegram_chat_id,
                        reason="bot_blocked_by_user",
                        trace_id=alert.trace_id,
                        timestamp=datetime.now(UTC),
                    )
                    await self._channel.default_exchange.publish(
                        Message(
                            body=blocked_event.model_dump_json().encode(),
                            delivery_mode=2,
                            headers={
                                "trace_id": str(alert.trace_id),
                                "timestamp": blocked_event.timestamp.isoformat(),
                                "retry_count": 0,
                            },
                        ),
                        routing_key=QUEUE_NAMES["user_maintenance"],
                    )
                await message.ack()

            else:
                response.raise_for_status()

        except httpx.HTTPStatusError as e:
            logger.error(
                "telegram_http_error",
                status_code=e.response.status_code,
                error=str(e),
            )
            await message.nack(requeue=True)
        except Exception as e:
            logger.error(
                "notification_failed",
                error=str(e),
                event_id=alert.event_id,
            )
            await message.nack(requeue=True)

    async def _process_maintenance(self, message: IncomingMessage) -> None:
        command = HardDeleteCommand.model_validate_json(message.body)

        logger.info(
            "maintenance_started",
            trace_id=str(command.trace_id),
            user_id=str(command.user_id),
            initiated_by=command.initiated_by,
        )

        async with async_session_factory() as session:
            result = await session.execute(
                select(User).where(User.id == command.user_id)
            )
            user = result.scalar_one_or_none()

            if not user:
                logger.warning("user_not_found_for_deletion", user_id=str(command.user_id))
                await message.ack()
                return

            await session.execute(
                delete(UserProduct).where(UserProduct.user_id == command.user_id)
            )
            await session.execute(delete(User).where(User.id == command.user_id))

            await session.execute(
                delete(UserProduct).where(
                    UserProduct.product_id.in_(
                        select(Product.id).where(
                            Product.id.notin_(
                                select(UserProduct.product_id)
                            )
                        )
                    )
                )
            )

            await session.commit()

            logger.info(
                "hard_delete_completed",
                user_id=str(command.user_id),
                telegram_chat_id=command.telegram_chat_id,
            )

        await message.ack()


async def async_run() -> None:
    global logger
    logger = configure_logging("NotificationWorker")

    for sig in (signal.SIGINT, signal.SIGTERM):
        loop = asyncio.get_event_loop()
        loop.add_signal_handler(sig, shutdown)

    connection = await aio_pika.connect_robust(settings.RABBITMQ_URI)
    channel = await connection.channel()
    await channel.set_qos(prefetch_count=settings.RABBITMQ_PREFETCH_COUNT)

    notif_queue = await channel.declare_queue(
        QUEUE_NAMES["telegram_notification"],
        durable=True,
        arguments={
            "x-dead-letter-exchange": "",
            "x-dead-letter-routing-key": f"{QUEUE_NAMES['telegram_notification']}.dlq",
        },
    )

    maint_queue = await channel.declare_queue(
        QUEUE_NAMES["user_maintenance"],
        durable=True,
        arguments={
            "x-dead-letter-exchange": "",
            "x-dead-letter-routing-key": f"{QUEUE_NAMES['user_maintenance']}.dlq",
        },
    )

    worker = NotificationWorker(QUEUE_NAMES["telegram_notification"])
    worker._channel = channel
    worker._http_session = httpx.AsyncClient()

    shutdown_event = asyncio.Event()

    async def handle_notif(message: IncomingMessage) -> None:
        try:
            await worker._process_notification(message)
        except Exception as e:
            logger.error("notification_error", error=str(e))
            await message.nack(requeue=False)

    async def handle_maint(message: IncomingMessage) -> None:
        try:
            await worker._process_maintenance(message)
        except Exception as e:
            logger.error("maintenance_error", error=str(e))
            await message.nack(requeue=False)

    try:
        logger.info("worker_started")

        notif_task = asyncio.create_task(notif_queue.consume(handle_notif))  # type: ignore[arg-type]
        maint_task = asyncio.create_task(maint_queue.consume(handle_maint))  # type: ignore[arg-type]

        await shutdown_event.wait()

    except asyncio.CancelledError:
        logger.info("worker_cancelled")
    finally:
        notif_task.cancel()
        maint_task.cancel()
        if worker._http_session:
            await worker._http_session.aclose()
            worker._http_session = None
        await channel.close()
        await connection.close()
        logger.info("worker_stopped")


def shutdown() -> None:
    global logger
    if logger:
        logger.info("shutdown_signal_received")


def run() -> None:
    import asyncio
    asyncio.run(async_run())


if __name__ == "__main__":
    run()
