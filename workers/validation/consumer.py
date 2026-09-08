import asyncio
import re
import signal
import uuid
from datetime import UTC, datetime
from typing import Any

import httpx
from aio_pika import IncomingMessage, Message
from aio_pika.abc import AbstractChannel
from bs4 import BeautifulSoup
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import settings
from core.database import async_session_factory
from core.logging import configure_logging
from core.rabbitmq import QUEUE_NAMES
from models.product import Product, ProductStatus
from models.user import User
from models.user_product import UserProduct
from schemas.commands import ItemValidationCommand
from schemas.events import AlertTriggeredEvent, AlertType
from workers.base import BaseWorker

logger: Any = None

AMAZON_ASIN_REGEX = r"/(?:dp|product|gp/product|exec/obidos/ASIN|gp/aw/d|dp/product)/([A-Z0-9]{10})"
AMAZON_URL_PATTERNS = (
    r"https?://(?:www\.)?amazon\.(?:com\.br|com|co\.uk|de|fr|it|es)/(?:.*?/)?"
    r"(?:dp|product|gp/product|exec/obidos/ASIN|gp/aw/d|dp/product)/([A-Z0-9]{10})"
)


def extract_asins_from_text(text: str) -> list[str]:
    asins = set()
    for match in re.finditer(AMAZON_URL_PATTERNS, text, re.IGNORECASE):
        asins.add(match.group(1))
    return list(asins)


async def fetch_title_and_image(session: httpx.AsyncClient, asin: str) -> tuple[str | None, str | None]:
    url = f"https://www.amazon.com.br/dp/{asin}"
    try:
        response = await session.get(
            url,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Accept-Language": "pt-BR,pt;q=0.9",
            },
            timeout=settings.SCRAPE_TIMEOUT_SECONDS,
            follow_redirects=True,
        )
        if response.status_code != 200:
            return None, None

        soup = BeautifulSoup(response.text, "lxml")
        title = None
        title_tag = soup.find("input", {"id": "productTitle"})
        if title_tag:
            raw_title = title_tag.get("value", "")
            if isinstance(raw_title, str):
                title = raw_title.strip()

        image_url = None
        image_tag = soup.find("img", {"id": "landingImage"})
        if image_tag:
            src = image_tag.get("src")
            if isinstance(src, str):
                image_url = src
            else:
                old_hires = image_tag.get("data-old-hires")
                if isinstance(old_hires, str):
                    image_url = old_hires

        return title if title else None, image_url
    except Exception:
        return None, None


async def resolve_url(session: httpx.AsyncClient, raw_url: str) -> str:
    try:
        response = await session.head(
            raw_url,
            headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"},
            timeout=settings.SCRAPE_TIMEOUT_SECONDS,
            follow_redirects=True,
        )
        return str(response.url)
    except Exception:
        return raw_url


class ValidationWorker(BaseWorker):
    def __init__(self) -> None:
        super().__init__("ValidationWorker", QUEUE_NAMES["item_validation"])
        self._http_session: httpx.AsyncClient | None = None

    async def connect(self) -> None:
        await super().connect()
        self._http_session = httpx.AsyncClient()

    async def disconnect(self) -> None:
        if self._http_session:
            await self._http_session.aclose()
            self._http_session = None
        await super().disconnect()

    async def _publish_alert(
        self,
        channel: AbstractChannel,
        command: ItemValidationCommand,
        title: str | None,
        product_id: uuid.UUID,
    ) -> None:
        asins = extract_asins_from_text(command.raw_url)
        alert = AlertTriggeredEvent(
            event_id=f"alert-{uuid.uuid4().hex[:8]}",
            alert_type=AlertType.SYSTEM_MESSAGE,
            user_id=uuid.UUID("00000000-0000-0000-0000-000000000000"),
            telegram_chat_id=command.telegram_chat_id,
            product_id=product_id,
            asin=asins[0] if asins else "UNKNOWN000",
            title=title,
            image_url=None,
            url=None,
            target_price=None,
            current_price=0.0,
            previous_price=None,
            message="Produto registrado com sucesso!" if title else "Produto registrado!",
            trace_id=command.trace_id,
            timestamp=datetime.now(UTC),
        )
        await channel.default_exchange.publish(
            Message(
                body=alert.model_dump_json().encode(),
                delivery_mode=2,
                headers={
                    "trace_id": str(command.trace_id),
                    "timestamp": alert.timestamp.isoformat(),
                    "retry_count": 0,
                },
            ),
            routing_key=QUEUE_NAMES["telegram_notification"],
        )

    async def _publish_error(
        self,
        channel: AbstractChannel,
        command: ItemValidationCommand,
        error_message: str,
    ) -> None:
        alert = AlertTriggeredEvent(
            event_id=f"alert-{uuid.uuid4().hex[:8]}",
            alert_type=AlertType.SYSTEM_MESSAGE,
            user_id=uuid.UUID("00000000-0000-0000-0000-000000000000"),
            telegram_chat_id=command.telegram_chat_id,
            product_id=uuid.UUID("00000000-0000-0000-0000-000000000000"),
            asin="UNKNOWN000",
            title=None,
            image_url=None,
            url=None,
            target_price=None,
            current_price=0.0,
            previous_price=None,
            message=error_message,
            trace_id=command.trace_id,
            timestamp=datetime.now(UTC),
        )
        await channel.default_exchange.publish(
            Message(
                body=alert.model_dump_json().encode(),
                delivery_mode=2,
                headers={
                    "trace_id": str(command.trace_id),
                    "timestamp": alert.timestamp.isoformat(),
                    "retry_count": 0,
                },
            ),
            routing_key=QUEUE_NAMES["telegram_notification"],
        )

    async def process_message(self, message: IncomingMessage) -> None:
        async with message.process(requeue=False):
            command = ItemValidationCommand.model_validate_json(message.body)

            logger.info(
                "validation_started",
                trace_id=str(command.trace_id),
                telegram_chat_id=command.telegram_chat_id,
                raw_url=command.raw_url,
            )

            try:
                asins = extract_asins_from_text(command.raw_url)
                if not asins:
                    logger.warning("no_asin_found", raw_url=command.raw_url)
                    if self._channel:
                        await self._publish_error(
                            self._channel, command, "Link inválido. Não foi possível extrair o ASIN."
                        )
                    return

                asin = asins[0]

                if self._http_session is None:
                    raise RuntimeError("HTTP session not initialized")
                resolved_url = await resolve_url(self._http_session, command.raw_url)
                final_asins = extract_asins_from_text(resolved_url)
                if final_asins:
                    asin = final_asins[0]

                logger.info("asin_extracted", asin=asin, resolved_url=resolved_url)

                async with async_session_factory() as session:
                    user = await self._get_or_create_user(session, command.telegram_chat_id)

                    product, is_new = await self._get_or_create_product(session, asin, resolved_url)

                    await self._create_subscription(
                        session,
                        user.id,
                        product.id,
                        command.target_price,
                        command.alert_on_all_time_low,
                    )

                    await session.commit()

                    logger.info(
                        "product_registered",
                        asin=asin,
                        user_id=str(user.id),
                        product_id=str(product.id),
                        is_new=is_new,
                    )

                    if self._channel:
                        await self._publish_alert(
                            self._channel, command, product.title, product.id
                        )

            except Exception as e:
                logger.error(
                    "validation_failed",
                    error=str(e),
                    trace_id=str(command.trace_id),
                )
                if self._channel:
                    await self._publish_error(
                        self._channel, command, f"Erro ao registrar produto: {str(e)}"
                    )

    async def _get_or_create_user(
        self, session: AsyncSession, telegram_chat_id: str
    ) -> User:
        result = await session.execute(
            select(User).where(User.telegram_chat_id == telegram_chat_id)
        )
        user = result.scalar_one_or_none()

        if not user:
            user = User(
                telegram_chat_id=telegram_chat_id,
                quota_limit=settings.MAX_USER_QUOTA,
                is_active=True,
            )
            session.add(user)
            await session.flush()

        user.last_seen_at = datetime.now(UTC)
        return user

    async def _get_or_create_product(
        self, session: AsyncSession, asin: str, url: str
    ) -> tuple[Product, bool]:
        result = await session.execute(
            select(Product).where(Product.asin == asin)
        )
        product = result.scalar_one_or_none()
        is_new = product is None

        if is_new:
            if self._http_session is None:
                raise RuntimeError("HTTP session not initialized")
            title, image_url = await fetch_title_and_image(self._http_session, asin)
            product = Product(
                asin=asin,
                url=url,
                title=title,
                image_url=image_url,
                status=ProductStatus.IDLE,
            )
            session.add(product)
            await session.flush()
        elif product is not None and product.url != url:
            product.url = url

        assert product is not None
        return product, is_new

    async def _create_subscription(
        self,
        session: AsyncSession,
        user_id: uuid.UUID,
        product_id: uuid.UUID,
        target_price: float | None,
        alert_on_all_time_low: bool,
    ) -> None:
        result = await session.execute(
            select(UserProduct).where(
                UserProduct.user_id == user_id,
                UserProduct.product_id == product_id,
            )
        )
        existing = result.scalar_one_or_none()

        if not existing:
            subscription = UserProduct(
                user_id=user_id,
                product_id=product_id,
                target_price=target_price,
                alert_on_all_time_low=alert_on_all_time_low,
                is_active=True,
            )
            session.add(subscription)


async def async_run() -> None:
    global logger
    logger = configure_logging("ValidationWorker")

    worker = ValidationWorker()

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
