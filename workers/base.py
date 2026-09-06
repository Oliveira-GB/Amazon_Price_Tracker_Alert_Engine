import asyncio
import signal
from abc import ABC, abstractmethod

import aio_pika
import structlog
from aio_pika import IncomingMessage
from aio_pika.abc import AbstractChannel, AbstractQueue, AbstractRobustConnection
from aio_pika.pool import Pool

from core.config import settings
from core.logging import configure_logging

logger: structlog.BoundLogger | None = None


class BaseWorker(ABC):
    def __init__(self, worker_name: str, queue_name: str):
        self.worker_name = worker_name
        self.queue_name = queue_name
        self._connection: AbstractRobustConnection | None = None
        self._channel: AbstractChannel | None = None
        self._queue: AbstractQueue | None = None
        self._shutdown_event = asyncio.Event()
        self._connection_pool: Pool[AbstractRobustConnection] | None = None
        self._channel_pool: Pool[AbstractChannel] | None = None

    async def connect(self) -> None:
        self._connection = await aio_pika.connect_robust(settings.RABBITMQ_URI)
        self._channel = await self._connection.channel()
        await self._channel.set_qos(prefetch_count=settings.RABBITMQ_PREFETCH_COUNT)
        self._queue = await self._channel.declare_queue(
            self.queue_name,
            durable=True,
            arguments={
                "x-dead-letter-exchange": "",
                "x-dead-letter-routing-key": f"{self.queue_name}.dlq",
            },
        )

    async def disconnect(self) -> None:
        if self._channel:
            await self._channel.close()
            self._channel = None
        if self._connection:
            await self._connection.close()
            self._connection = None

    @abstractmethod
    async def process_message(self, message: IncomingMessage) -> None:
        pass

    async def _on_message(self, message: IncomingMessage) -> None:
        try:
            await self.process_message(message)
        except Exception as e:
            if logger:
                logger.error(
                    "message_processing_failed",
                    error=str(e),
                    queue=self.queue_name,
                )
            await message.nack(requeue=False)

    async def start(self) -> None:
        global logger
        logger = configure_logging(self.worker_name)

        loop = asyncio.get_event_loop()

        for sig in (signal.SIGINT, signal.SIGTERM):
            loop.add_signal_handler(sig, self._handle_shutdown)

        logger.info("worker_starting", queue=self.queue_name)

        try:
            await self.connect()
            logger.info("worker_connected", queue=self.queue_name)

            if self._queue is None:
                raise RuntimeError("Queue not initialized after connect()")
            async with self._queue.iterator() as queue_iter:
                logger.info("worker_consuming", queue=self.queue_name)
                async for message in queue_iter:
                    if self._shutdown_event.is_set():
                        await message.nack(requeue=True)
                        break
                    await self._on_message(message)  # type: ignore[arg-type]

        except asyncio.CancelledError:
            logger.info("worker_cancelled")
        except Exception as e:
            logger.error("worker_error", error=str(e))
            raise
        finally:
            await self.disconnect()
            logger.info("worker_stopped")

    def _handle_shutdown(self) -> None:
        if logger:
            logger.info("shutdown_signal_received")
        self._shutdown_event.set()

    async def stop(self) -> None:
        self._shutdown_event.set()


async def run_worker(worker_class: type[BaseWorker], queue_name: str) -> None:
    worker = worker_class(worker_class.__name__, queue_name)
    await worker.start()
