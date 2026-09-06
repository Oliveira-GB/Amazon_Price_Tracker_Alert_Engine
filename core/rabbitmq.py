
from collections.abc import AsyncGenerator

import aio_pika
from aio_pika import Channel, Connection, ExchangeType
from aio_pika.pool import Pool

from core.config import settings

RABBITMQ_EXCHANGE = "tracker.direct.exchange"

QUEUE_NAMES = {
    "item_validation": "item.validation.queue",
    "scrape_jobs": "scrape.jobs.queue",
    "price_decision": "price.decision.queue",
    "telegram_notification": "telegram.notification.queue",
    "user_maintenance": "user.maintenance.queue",
}

DLQ_NAMES = {
    "item_validation": "item.validation.dlq",
    "scrape_jobs": "scrape.jobs.dlq",
    "price_decision": "price.decision.dlq",
    "telegram_notification": "telegram.notification.dlq",
    "user_maintenance": "user.maintenance.dlq",
}

_connection_pool: Pool[Connection] | None = None
_channel_pool: Pool[Channel] | None = None


async def init_rabbitmq() -> None:
    global _connection_pool, _channel_pool

    async def connection_factory() -> aio_pika.RobustConnection:
        return await aio_pika.connect_robust(settings.RABBITMQ_URI)

    async def channel_factory(connection: aio_pika.RobustConnection) -> Channel:
        return await connection.channel()  # type: ignore[return-value]

    _connection_pool = Pool(
        connection_factory,
        max_size=10,
    )
    _channel_pool = Pool(
        channel_factory,
        max_size=20,
    )


async def close_rabbitmq() -> None:
    global _connection_pool, _channel_pool
    if _channel_pool:
        await _channel_pool.close()
        _channel_pool = None
    if _connection_pool:
        await _connection_pool.close()
        _connection_pool = None


async def get_channel() -> AsyncGenerator[Channel, None]:
    if _channel_pool is None:
        await init_rabbitmq()
    assert _channel_pool is not None
    async with _channel_pool.acquire() as channel:
        yield channel


async def get_connection() -> AsyncGenerator[Connection, None]:
    if _connection_pool is None:
        await init_rabbitmq()
    assert _connection_pool is not None
    async with _connection_pool.acquire() as connection:
        yield connection


async def setup_exchange_and_queues() -> None:
    connection = await aio_pika.connect_robust(settings.RABBITMQ_URI)
    channel = await connection.channel()

    exchange = await channel.declare_exchange(
        RABBITMQ_EXCHANGE,
        ExchangeType.DIRECT,
        durable=True,
    )

    for queue_key, queue_name in QUEUE_NAMES.items():
        dlq_name = DLQ_NAMES[queue_key]
        await channel.declare_queue(
            dlq_name,
            durable=True,
            arguments={"x-message-ttl": settings.DLQ_MESSAGE_TTL_DAYS * 86400000},
        )

        queue = await channel.declare_queue(
            queue_name,
            durable=True,
            arguments={
                "x-dead-letter-exchange": "",
                "x-dead-letter-routing-key": dlq_name,
            },
        )
        await queue.bind(exchange, routing_key=queue_name)

    await channel.close()
    await connection.close()
