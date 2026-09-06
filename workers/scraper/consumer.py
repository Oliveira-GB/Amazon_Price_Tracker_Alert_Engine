import asyncio
import random
import re
import signal
import uuid
from datetime import UTC, datetime
from typing import Any

import httpx
from aio_pika import IncomingMessage, Message
from bs4 import BeautifulSoup
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import settings
from core.database import async_session_factory
from core.logging import configure_logging
from core.rabbitmq import QUEUE_NAMES
from models.price_history import PriceHistory
from models.product import Product, ProductStatus
from schemas.commands import ScrapeCommand
from schemas.events import PriceUpdatedEvent
from workers.base import BaseWorker

logger: Any = None

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
]

PRICE_FULL_SELECTORS = [
    "#priceblock_ourprice",
    "#priceblock_dealprice",
    "#corePrice_feature_div .a-offscreen",
    ".a-price .a-offscreen",
    "#corePriceDisplay_desktop_feature_div .a-offscreen",
    "#apex_offerDisplay_desktop .a-offscreen",
]

PRICE_DISCOUNT_SELECTORS = [
    "#priceblock_saleprice",
    "#priceblock_vatmsg",
    ".priceblock_compare_at",
]


class CircuitBreaker:
    def __init__(self, threshold: int, timeout: int) -> None:
        self.threshold = threshold
        self.timeout = timeout
        self.failures = 0
        self.opened_at: datetime | None = None

    def is_open(self) -> bool:
        if self.opened_at is None:
            return False
        if (datetime.now(UTC) - self.opened_at).total_seconds() >= self.timeout:
            self.opened_at = None
            self.failures = 0
            return False
        return True

    def record_failure(self) -> None:
        self.failures += 1
        if self.failures >= self.threshold:
            self.opened_at = datetime.now(UTC)

    def record_success(self) -> None:
        self.failures = 0
        self.opened_at = None


def extract_price(text: str) -> float | None:
    match = re.search(r"[\d.,]+", text.replace(",", "."))
    if match:
        price_str = match.group().replace(",", "")
        try:
            return float(price_str)
        except ValueError:
            return None
    return None


class ScraperWorker(BaseWorker):
    def __init__(self) -> None:
        super().__init__("ScraperWorker", QUEUE_NAMES["scrape_jobs"])
        self._http_session: httpx.AsyncClient | None = None
        self._circuit_breaker = CircuitBreaker(
            settings.CIRCUIT_BREAKER_THRESHOLD,
            settings.CIRCUIT_BREAKER_TIMEOUT_SECONDS,
        )

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
            command = ScrapeCommand.model_validate_json(message.body)

            logger.info(
                "scrape_started",
                trace_id=str(command.trace_id),
                asin=command.asin,
                product_id=str(command.product_id),
            )

            if self._circuit_breaker.is_open():
                logger.warning(
                    "circuit_breaker_open",
                    wait_seconds=settings.CIRCUIT_BREAKER_TIMEOUT_SECONDS,
                )
                await asyncio.sleep(settings.CIRCUIT_BREAKER_TIMEOUT_SECONDS)
                await message.nack(requeue=True)
                return

            try:
                result = await self._scrape_product(command)

                if result is None:
                    await message.ack()
                    return

                price_full, price_discount, is_out_of_stock = result

                async with async_session_factory() as session:
                    await self._update_price(
                        session,
                        command,
                        price_full,
                        price_discount,
                        is_out_of_stock,
                    )

                await message.ack()
                self._circuit_breaker.record_success()

            except Exception as e:
                logger.error(
                    "scrape_failed",
                    error=str(e),
                    asin=command.asin,
                )
                self._circuit_breaker.record_failure()

                if isinstance(e, httpx.HTTPStatusError) and e.response.status_code == 404:
                    async with async_session_factory() as session:
                        await self._mark_unavailable(session, command.product_id)
                    await message.ack()
                else:
                    await message.nack(requeue=True)

    async def _scrape_product(
        self, command: ScrapeCommand
    ) -> tuple[float | None, float | None, bool] | None:
        await asyncio.sleep(random.uniform(1, 3))

        url = f"https://www.amazon.com.br/dp/{command.asin}"
        headers = {
            "User-Agent": random.choice(USER_AGENTS),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "pt-BR,pt;q=0.9",
            "Accept-Encoding": "gzip, deflate, br",
        }

        response = await self._http_session.get(
            url,
            headers=headers,
            timeout=settings.SCRAPE_TIMEOUT_SECONDS,
            follow_redirects=True,
        )

        if response.status_code == 503:
            raise httpx.HTTPStatusError(
                "Amazon blocked request",
                request=response.request,
                response=response,
            )

        if response.status_code == 404:
            return None

        response.raise_for_status()

        soup = BeautifulSoup(response.text, "lxml")

        if soup.find(string=re.compile("automated requests")) or soup.find(
            "div", {"id": "captchachar"}
        ):
            raise httpx.HTTPStatusError(
                "Amazon captcha/blocked",
                request=response.request,
                response=response,
            )

        price_full = None
        for selector in PRICE_FULL_SELECTORS:
            el = soup.select_one(selector)
            if el:
                price_full = extract_price(el.get_text())
                if price_full:
                    break

        price_discount = None
        for selector in PRICE_DISCOUNT_SELECTORS:
            el = soup.select_one(selector)
            if el:
                price_discount = extract_price(el.get_text())
                if price_discount:
                    break

        out_of_stock = (
            soup.find(string=re.compile("não|estoque|indisponível|unavailable", re.I))
            is not None
        ) or (
            soup.find("div", {"id": "outOfStock"}) is not None
            or soup.find("div", {"id": "availability"}) is not None
            and "não" in soup.find("div", {"id": "availability"}).get_text().lower()
        )

        return price_full, price_discount, out_of_stock

    async def _update_price(
        self,
        session: AsyncSession,
        command: ScrapeCommand,
        price_full: float | None,
        price_discount: float | None,
        is_out_of_stock: bool,
    ) -> None:
        result = await session.execute(
            select(Product).where(Product.id == command.product_id)
        )
        product = result.scalar_one_or_none()

        if product is None:
            return

        previous_full = product.last_price_full
        previous_discount = product.last_price_discount

        price_changed = (
            previous_full != price_full or previous_discount != price_discount
        )

        product.last_checked_at = datetime.now(UTC)

        if price_changed:
            product.last_price_full = price_full
            product.last_price_discount = price_discount

            if (
                price_discount is not None
                and (product.all_time_low is None or price_discount < product.all_time_low)
            ):
                product.all_time_low = price_discount

            price_record = PriceHistory(
                product_id=command.product_id,
                price_full=price_full,
                price_discount=price_discount,
                is_discounted=price_discount is not None and price_full is not None and price_discount < price_full,
                is_out_of_stock=is_out_of_stock,
            )
            session.add(price_record)

            await session.commit()

            logger.info(
                "price_updated",
                asin=command.asin,
                price_full=price_full,
                price_discount=price_discount,
                is_out_of_stock=is_out_of_stock,
            )

            if self._channel:
                event = PriceUpdatedEvent(
                    event_id=f"price-{uuid.uuid4().hex[:8]}",
                    asin=command.asin,
                    product_id=command.product_id,
                    price_full=price_full,
                    price_discount=price_discount,
                    is_out_of_stock=is_out_of_stock,
                    previous_price_full=previous_full,
                    previous_price_discount=previous_discount,
                    trace_id=command.trace_id,
                    timestamp=datetime.now(UTC),
                )
                await self._channel.default_exchange.publish(
                    Message(
                        body=event.model_dump_json().encode(),
                        delivery_mode=2,
                        headers={
                            "trace_id": str(command.trace_id),
                            "timestamp": event.timestamp.isoformat(),
                            "retry_count": 0,
                        },
                    ),
                    routing_key=QUEUE_NAMES["price_decision"],
                )
        else:
            await session.commit()
            logger.info(
                "price_unchanged",
                asin=command.asin,
            )

    async def _mark_unavailable(self, session: AsyncSession, product_id: uuid.UUID) -> None:
        result = await session.execute(
            select(Product).where(Product.id == product_id)
        )
        product = result.scalar_one_or_none()

        if product:
            product.status = ProductStatus.UNAVAILABLE
            await session.commit()
            logger.info("product_marked_unavailable", product_id=str(product_id))


async def run() -> None:
    global logger
    logger = configure_logging("ScraperWorker")

    worker = ScraperWorker()

    loop = asyncio.get_event_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, worker.stop)

    try:
        await worker.connect()
        logger.info("worker_connected", queue=worker.queue_name)

        async with worker._queue.iterator() as queue_iter:
            logger.info("worker_consuming", queue=worker.queue_name)
            async for message in queue_iter:
                if worker._shutdown_event.is_set():
                    await message.nack(requeue=True)
                    break
                await worker.process_message(message)

    except asyncio.CancelledError:
        logger.info("worker_cancelled")
    except Exception as e:
        logger.error("worker_error", error=str(e))
        raise
    finally:
        await worker.disconnect()
        logger.info("worker_stopped")
