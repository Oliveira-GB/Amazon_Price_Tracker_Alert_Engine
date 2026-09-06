import asyncio
import uuid
from datetime import UTC, datetime
from typing import Any

import aio_pika
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from sqlalchemy import select

from core.config import settings
from core.database import async_session_factory
from core.logging import configure_logging
from core.rabbitmq import QUEUE_NAMES
from models.product import Product, ProductStatus
from schemas.commands import ScrapeCommand

logger: Any = None
scheduler = AsyncIOScheduler()


async def publish_scrape_jobs() -> None:
    global logger
    if logger is None:
        logger = configure_logging("SchedulerWorker")

    logger.info("scheduler_tick_started")

    connection = await aio_pika.connect_robust(settings.RABBITMQ_URI)
    channel = await connection.channel()

    try:
        batch_size = 50
        offset = 0
        total_published = 0

        while True:
            async with async_session_factory() as session:
                stmt = (
                    select(Product)
                    .where(Product.status == ProductStatus.ACTIVE)
                    .limit(batch_size)
                    .offset(offset)
                )
                result = await session.execute(stmt)
                products = result.scalars().all()

                if not products:
                    break

                for product in products:
                    command = ScrapeCommand(
                        event_id=f"scrape-{uuid.uuid4().hex[:8]}",
                        asin=product.asin,
                        product_id=product.id,
                        priority=5,
                        trace_id=uuid.uuid4(),
                        timestamp=datetime.now(UTC),
                    )

                    await channel.default_exchange.publish(
                        aio_pika.Message(
                            body=command.model_dump_json().encode(),
                            delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
                            headers={
                                "trace_id": str(command.trace_id),
                                "timestamp": command.timestamp.isoformat(),
                                "retry_count": 0,
                            },
                        ),
                        routing_key=QUEUE_NAMES["scrape_jobs"],
                    )
                    total_published += 1

                offset += batch_size

                if len(products) < batch_size:
                    break

        logger.info("scheduler_tick_completed", jobs_published=total_published)

    except Exception as e:
        logger.error("scheduler_tick_failed", error=str(e))
        raise
    finally:
        await channel.close()
        await connection.close()


async def run() -> None:
    global logger
    logger = configure_logging("SchedulerWorker")

    logger.info(
        "scheduler_starting",
        interval_hours=settings.SCRAPE_INTERVAL_HOURS,
    )

    scheduler.add_job(
        publish_scrape_jobs,
        trigger=IntervalTrigger(hours=settings.SCRAPE_INTERVAL_HOURS),
        id="publish_scrape_jobs",
        replace_existing=True,
    )

    scheduler.start()

    logger.info("scheduler_started")

    try:
        await asyncio.Future()
    except asyncio.CancelledError:
        logger.info("scheduler_cancelled")
    finally:
        scheduler.shutdown(wait=False)
        logger.info("scheduler_stopped")
