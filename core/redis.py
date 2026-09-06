from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from redis.asyncio import ConnectionPool, Redis

from core.config import settings

pool: ConnectionPool | None = None
_client: Redis | None = None


async def init_redis() -> None:
    global pool, _client
    pool = ConnectionPool.from_url(
        settings.REDIS_URL,
        decode_responses=True,
        max_connections=20,
    )
    _client = Redis(connection_pool=pool)


async def close_redis() -> None:
    global pool, _client
    if _client:
        await _client.aclose()
        _client = None
    if pool:
        await pool.disconnect()
        pool = None


async def get_redis() -> Redis:
    if _client is None:
        await init_redis()
    return _client


@asynccontextmanager
async def get_redis_context() -> AsyncGenerator[Redis, None]:
    client = await get_redis()
    yield client
