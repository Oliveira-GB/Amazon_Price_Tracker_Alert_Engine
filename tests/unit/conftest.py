import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest


@pytest.fixture
def mock_rabbitmq_channel():
    channel = AsyncMock()
    channel.default_exchange = AsyncMock()
    channel.default_exchange.publish = AsyncMock()
    return channel


@pytest.fixture
def mock_redis():
    redis = AsyncMock()
    redis.exists = AsyncMock(return_value=False)
    redis.setex = AsyncMock(return_value=True)
    return redis


@pytest.fixture
def mock_http_client():
    client = AsyncMock()
    client.get = AsyncMock()
    client.post = AsyncMock()
    client.head = AsyncMock()
    client.aclose = AsyncMock()
    return client


@pytest.fixture
def sample_uuid():
    return uuid.UUID("123e4567-e89b-12d3-a456-426614174000")


@pytest.fixture
def sample_trace_id():
    return uuid.uuid4()


@pytest.fixture
def sample_timestamp():
    return datetime.now(UTC)
