import asyncio
import signal
import uuid
from datetime import UTC, datetime
from typing import Any

from aio_pika import IncomingMessage, Message
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import settings
from core.database import async_session_factory
from core.logging import configure_logging
from core.rabbitmq import QUEUE_NAMES
from core.redis import get_redis
from models.product import Product
from models.user_product import UserProduct
from schemas.events import AlertTriggeredEvent, AlertType, PriceUpdatedEvent
from workers.base import BaseWorker

logger: Any = None


class DecisionWorker(BaseWorker):
    def __init__(self) -> None:
        super().__init__("DecisionWorker", QUEUE_NAMES["price_decision"])

    async def process_message(self, message: IncomingMessage) -> None:
        async with message.process(requeue=False):
            event = PriceUpdatedEvent.model_validate_json(message.body)

            logger.info(
                "decision_started",
                trace_id=str(event.trace_id),
                asin=event.asin,
                product_id=str(event.product_id),
                price_full=event.price_full,
                price_discount=event.price_discount,
            )

            try:
                async with async_session_factory() as session:
                    result = await session.execute(
                        select(Product).where(Product.id == event.product_id)
                    )
                    product = result.scalar_one_or_none()

                    if not product:
                        logger.warning("product_not_found", product_id=str(event.product_id))
                        return

                    await self._process_price_change(
                        session, event, product
                    )

                await message.ack()

            except Exception as e:
                logger.error(
                    "decision_failed",
                    error=str(e),
                    asin=event.asin,
                )
                await message.nack(requeue=True)

    async def _process_price_change(
        self,
        session: AsyncSession,
        event: PriceUpdatedEvent,
        product: Product,
    ) -> None:
        subscriptions_result = await session.execute(
            select(UserProduct).where(
                UserProduct.product_id == event.product_id,
                UserProduct.is_active,
            )
        )
        subscriptions = subscriptions_result.scalars().all()

        logger.info(
            "checking_subscriptions",
            count=len(subscriptions),
            asin=event.asin,
        )

        redis = await get_redis()
        cooldown_seconds = settings.ALERT_COOLDOWN_HOURS * 3600

        for sub in subscriptions:
            current_price = event.price_discount if event.price_discount else event.price_full

            if current_price is None:
                continue

            should_alert = False

            if sub.target_price is not None and current_price <= sub.target_price:
                should_alert = True

            if sub.alert_on_all_time_low and product.all_time_low is not None:
                if current_price <= product.all_time_low:
                    should_alert = True

            if not should_alert:
                continue

            lock_key = f"lock:alert:{sub.user_id}:{event.asin}"
            try:
                if await redis.exists(lock_key):
                    logger.info(
                        "cooldown_active",
                        user_id=str(sub.user_id),
                        asin=event.asin,
                    )
                    continue

                await redis.setex(lock_key, cooldown_seconds, "1")
            except Exception as e:
                logger.warning(
                    "redis_unavailable_using_fallback",
                    error=str(e),
                    user_id=str(sub.user_id),
                )
                if sub.last_notified_at:
                    last_notified = sub.last_notified_at.replace(tzinfo=UTC)
                    if (datetime.now(UTC) - last_notified).total_seconds() < cooldown_seconds:
                        continue

            alert = AlertTriggeredEvent(
                event_id=f"alert-{uuid.uuid4().hex[:8]}",
                alert_type=AlertType.ALL_TIME_LOW if sub.alert_on_all_time_low else AlertType.TARGET_PRICE,
                user_id=sub.user_id,
                telegram_chat_id="",
                product_id=event.product_id,
                asin=event.asin,
                title=product.title,
                image_url=product.image_url,
                url=product.url,
                target_price=sub.target_price,
                current_price=current_price,
                previous_price=event.previous_price_discount if event.previous_price_discount else event.previous_price_full,
                message=self._build_message(
                    event.asin,
                    current_price,
                    sub.target_price,
                    product.title,
                ),
                trace_id=event.trace_id,
                timestamp=datetime.now(UTC),
            )

            if self._channel:
                await self._channel.default_exchange.publish(
                    Message(
                        body=alert.model_dump_json().encode(),
                        delivery_mode=2,
                        headers={
                            "trace_id": str(event.trace_id),
                            "timestamp": alert.timestamp.isoformat(),
                            "retry_count": 0,
                        },
                    ),
                    routing_key=QUEUE_NAMES["telegram_notification"],
                )

            sub.last_notified_at = datetime.now(UTC)

            logger.info(
                "alert_triggered",
                user_id=str(sub.user_id),
                asin=event.asin,
                current_price=current_price,
                target_price=sub.target_price,
            )

        await session.commit()

    def _build_message(
        self,
        asin: str,
        current_price: float,
        target_price: float | None,
        title: str | None,
    ) -> str:
        title_display = title[:50] + "..." if title and len(title) > 50 else title
        if target_price is not None:
            return f"Preço de R$ {current_price:.2f} atingiu seu alvo de R$ {target_price:.2f}!{f' ({title_display})' if title_display else ''}"
        return f"Novo preço histórico: R$ {current_price:.2f}!{f' ({title_display})' if title_display else ''}"


async def async_run() -> None:
    global logger
    logger = configure_logging("DecisionWorker")

    worker = DecisionWorker()

    loop = asyncio.get_event_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, worker.stop)

    try:
        await worker.connect()
        logger.info("worker_connected", queue=worker.queue_name)

        if worker._queue is None:
            raise RuntimeError("Queue not initialized")
        async with worker._queue.iterator() as queue_iter:
            logger.info("worker_consuming", queue=worker.queue_name)
            async for message in queue_iter:
                if worker._shutdown_event.is_set():
                    await message.nack(requeue=True)
                    break
                await worker.process_message(message)  # type: ignore[arg-type]

    except asyncio.CancelledError:
        logger.info("worker_cancelled")
    except Exception as e:
        logger.error("worker_error", error=str(e))
        raise
    finally:
        await worker.disconnect()
        logger.info("worker_stopped")


def run() -> None:
    import asyncio
    asyncio.run(async_run())


if __name__ == "__main__":
    run()
