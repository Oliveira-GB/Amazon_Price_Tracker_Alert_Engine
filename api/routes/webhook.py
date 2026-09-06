import uuid
from datetime import UTC, datetime
from typing import Any

import aio_pika
from fastapi import APIRouter, Request
from pydantic import BaseModel

from api.dependencies import TelegramSecret
from core.config import settings
from core.database import async_session_factory
from core.logging import configure_logging
from core.rabbitmq import QUEUE_NAMES
from models.user import User
from models.user_product import UserProduct
from schemas.commands import ItemValidationCommand

logger = configure_logging("webhook")

router = APIRouter()


class TelegramWebhookPayload(BaseModel):
    update_id: int
    message: dict | None = None
    edited_message: dict | None = None
    callback_query: dict | None = None


class TelegramWebhookResponse(BaseModel):
    ok: bool
    message: str = "OK"


def extract_price_from_text(text: str) -> float | None:
    import re
    match = re.search(r"[\d.,]+", text.replace(",", "."))
    if match:
        price_str = match.group().replace(",", "")
        try:
            return float(price_str)
        except ValueError:
            return None
    return None


async def get_or_create_user(session: Any, chat_id: str) -> User:
    from sqlalchemy import select

    result = await session.execute(
        select(User).where(User.telegram_chat_id == chat_id)
    )
    user = result.scalar_one_or_none()

    if not user:
        user = User(
            telegram_chat_id=chat_id,
            quota_limit=settings.MAX_USER_QUOTA,
            is_active=True,
        )
        session.add(user)
        await session.flush()

    user.last_seen_at = datetime.now(UTC)
    return user


async def get_user_subscription_count(session: Any, user_id: uuid.UUID) -> int:
    from sqlalchemy import func, select

    result = await session.execute(
        select(func.count()).select_from(UserProduct).where(
            UserProduct.user_id == user_id,
            UserProduct.is_active,
        )
    )
    return result.scalar() or 0


async def publish_to_queue(command: ItemValidationCommand) -> None:
    connection = await aio_pika.connect_robust(settings.RABBITMQ_URI)
    channel = await connection.channel()

    try:
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
            routing_key=QUEUE_NAMES["item_validation"],
        )
    finally:
        await channel.close()


@router.post("/webhook/telegram", response_model=TelegramWebhookResponse)
async def receive_telegram_webhook(
    payload: TelegramWebhookPayload,
    request: Request,
    _token: TelegramSecret,
) -> TelegramWebhookResponse:
    trace_id = uuid.uuid4()

    try:
        update_id = payload.update_id
        logger.info(
            "telegram_webhook_received",
            trace_id=str(trace_id),
            update_id=update_id,
        )

        if payload.message:
            await process_message(payload.message, trace_id)
        elif payload.callback_query:
            await process_callback_query(payload.callback_query, trace_id)

        return TelegramWebhookResponse(ok=True, message="OK")

    except Exception as e:
        logger.error(
            "telegram_webhook_error",
            trace_id=str(trace_id),
            error=str(e),
        )
        return TelegramWebhookResponse(ok=True, message="OK")


async def process_message(message: dict, trace_id: uuid.UUID) -> None:
    chat_id = str(message.get("chat", {}).get("id", ""))
    text = message.get("text", "")

    logger.info(
        "telegram_message_received",
        trace_id=str(trace_id),
        chat_id=chat_id,
        text=text[:100] if text else None,
    )

    if not chat_id:
        return

    if text.startswith("/"):
        await handle_command(chat_id, text, trace_id)
    elif text.startswith("http"):
        await handle_url(chat_id, text, trace_id)
    else:
        await send_help_message(chat_id, trace_id)


async def handle_command(chat_id: str, command: str, trace_id: uuid.UUID) -> None:
    cmd = command.split()[0].lower()

    if cmd == "/start":
        await send_text_message(
            chat_id,
            "Bem-vindo ao Amazon Price Tracker!\n\n"
            "Envie um link de produto da Amazon para começar a rastrear.\n"
            "Configure um preço alvo e receba alertas quando o preço cair.",
            trace_id,
        )
    elif cmd == "/list":
        await send_list_message(chat_id, trace_id)
    elif cmd == "/pause":
        await send_text_message(
            chat_id,
            "Use /list para gerenciar seus produtos rastreados.",
            trace_id,
        )
    elif cmd == "/request_upgrade":
        await send_text_message(
            chat_id,
            "Você atingiu o limite de 50 produtos.\n\n"
            "Entre em contato com o administrador para aumentar sua quota.",
            trace_id,
        )
    elif cmd == "/help":
        await send_help_message(chat_id, trace_id)
    else:
        await send_text_message(
            chat_id,
            "Comando não reconhecido. Use /help para ver os comandos disponíveis.",
            trace_id,
        )


async def send_list_message(chat_id: str, trace_id: uuid.UUID) -> None:
    from sqlalchemy import select

    async with async_session_factory() as session:
        user = await get_or_create_user(session, chat_id)
        result = await session.execute(
            select(UserProduct, UserProduct)
            .where(UserProduct.user_id == user.id)
            .where(UserProduct.is_active)
        )
        subscriptions = result.scalars().all()

        if not subscriptions:
            text = "Você ainda não tem produtos rastreados.\n\n"
            text += "Envie um link da Amazon para começar!"
        else:
            text = f"Você está rastreando {len(subscriptions)}/{user.quota_limit} produtos:\n\n"
            for i, sub in enumerate(subscriptions[:10], 1):
                text += f"{i}. ASIN: {sub.product_id}\n"
                if sub.target_price:
                    text += f"   Alvo: R$ {sub.target_price:.2f}\n"

            if len(subscriptions) > 10:
                text += f"\n... e mais {len(subscriptions) - 10} produtos"

        await send_text_message(chat_id, text, trace_id)


async def handle_url(chat_id: str, url: str, trace_id: uuid.UUID) -> None:
    logger.info("url_submitted", trace_id=str(trace_id), chat_id=chat_id, url_length=len(url))

    target_price = extract_price_from_text(url)
    url_clean = url.split()[0] if " " in url else url

    async with async_session_factory() as session:
        user = await get_or_create_user(session, chat_id)
        count = await get_user_subscription_count(session, user.id)

        if count >= user.quota_limit:
            await send_text_message(
                chat_id,
                f"Você atingiu o limite de {user.quota_limit} produtos.\n\n"
                "Use /request_upgrade para solicitar um aumento de quota.",
                trace_id,
            )
            return

    command = ItemValidationCommand(
        event_id=f"val-{uuid.uuid4().hex[:8]}",
        telegram_chat_id=chat_id,
        raw_url=url_clean,
        target_price=target_price,
        alert_on_all_time_low=False,
        trace_id=trace_id,
        timestamp=datetime.now(UTC),
    )

    await publish_to_queue(command)

    await send_text_message(chat_id, "Processando link... você será notificado quando o produto for registrado.", trace_id)


async def send_help_message(chat_id: str, trace_id: uuid.UUID) -> None:
    text = (
        "*Comandos disponíveis:*\n\n"
        "/start - Iniciar o bot\n"
        "/list - Ver produtos rastreados\n"
        "/pause - Pausar alertas\n"
        "/help - Mostrar esta ajuda\n\n"
        "*Como rastrear um produto:*\n"
        "Envie um link da Amazon e, opcionalmente, o preço alvo.\n"
        "Exemplo: `https://amazon.com.br/dp/B08ABC1234 299.90`"
    )
    await send_text_message(chat_id, text, trace_id)


async def send_text_message(chat_id: str, text: str, trace_id: uuid.UUID) -> None:
    import httpx

    if not settings.TG_BOT_TOKEN:
        logger.warning("telegram_token_not_configured_cannot_send_message")
        return

    try:
        async with httpx.AsyncClient() as client:
            await client.post(
                f"https://api.telegram.org/bot{settings.TG_BOT_TOKEN}/sendMessage",
                json={
                    "chat_id": chat_id,
                    "text": text,
                    "parse_mode": "Markdown",
                },
                timeout=10.0,
            )
    except Exception as e:
        logger.error(
            "failed_to_send_telegram_message",
            trace_id=str(trace_id),
            chat_id=chat_id,
            error=str(e),
        )


async def process_callback_query(callback_query: dict, trace_id: uuid.UUID) -> None:
    pass
