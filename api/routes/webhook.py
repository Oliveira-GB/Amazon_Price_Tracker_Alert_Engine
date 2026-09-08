import uuid

import aio_pika
from fastapi import APIRouter, Request
from pydantic import BaseModel

from api.bot.client import TelegramBot, get_telegram_bot
from api.bot.handlers import (
    handle_callback,
    handle_delete,
    handle_help,
    handle_list,
    handle_pause,
    handle_request_upgrade,
    handle_start,
    handle_url,
)
from api.dependencies import TelegramSecret
from core.config import settings
from core.logging import configure_logging
from core.rabbitmq import QUEUE_NAMES
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

        bot = get_telegram_bot()

        if payload.message:
            await process_message(payload.message, trace_id, bot)
        elif payload.callback_query:
            await process_callback_query(payload.callback_query, trace_id, bot)

        return TelegramWebhookResponse(ok=True, message="OK")

    except Exception as e:
        logger.error(
            "telegram_webhook_error",
            trace_id=str(trace_id),
            error=str(e),
        )
        return TelegramWebhookResponse(ok=True, message="OK")


async def process_message(
    message: dict,
    trace_id: uuid.UUID,
    bot: TelegramBot,
) -> None:
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
        await handle_command(chat_id, text, trace_id, bot)
    elif text.startswith("http"):
        await handle_url(bot, chat_id, text, trace_id)
    else:
        await handle_help(bot, chat_id, trace_id)


async def handle_command(
    chat_id: str,
    command: str,
    trace_id: uuid.UUID,
    bot: TelegramBot,
) -> None:
    cmd = command.split()[0].lower()
    parts = command.split()
    args = parts[1:] if len(parts) > 1 else []

    if cmd == "/start":
        await handle_start(bot, chat_id, trace_id)
    elif cmd == "/list":
        await handle_list(bot, chat_id, trace_id)
    elif cmd == "/pause":
        idx = int(args[0]) if args and args[0].isdigit() else None
        await handle_pause(bot, chat_id, trace_id, idx)
    elif cmd == "/delete":
        idx = int(args[0]) if args and args[0].isdigit() else None
        await handle_delete(bot, chat_id, trace_id, idx)
    elif cmd == "/request_upgrade":
        await handle_request_upgrade(bot, chat_id, trace_id)
    elif cmd == "/help":
        await handle_help(bot, chat_id, trace_id)
    else:
        await bot.send_message(
            chat_id,
            "Comando não reconhecido. Use /help para ver os comandos disponíveis.",
        )


async def process_callback_query(
    callback_query: dict,
    trace_id: uuid.UUID,
    bot: TelegramBot,
) -> None:
    await handle_callback(bot, callback_query, trace_id)
