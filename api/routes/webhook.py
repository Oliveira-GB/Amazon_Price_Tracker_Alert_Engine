import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Header, Request
from pydantic import BaseModel, Field

from core.config import settings
from core.logging import configure_logging

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


def verify_telegram_token(x_telegram_bot_api_secret_token: str | None = Header(None)) -> str:
    if not settings.TG_BOT_TOKEN:
        logger.warning("telegram_token_not_configured")
        return "dev_token"

    if x_telegram_bot_api_secret_token != settings.TG_BOT_TOKEN:
        raise HTTPException(status_code=403, detail="Forbidden")

    return x_telegram_bot_api_secret_token


@router.post("/webhook/telegram", response_model=TelegramWebhookResponse)
async def receive_telegram_webhook(
    payload: TelegramWebhookPayload,
    request: Request,
    _: str = Depends(verify_telegram_token),
) -> TelegramWebhookResponse:
    trace_id = uuid.uuid4()

    try:
        update_id = payload.update_id
        logger.info(
            "telegram_webhook_received",
            trace_id=trace_id,
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
            trace_id=trace_id,
            error=str(e),
        )
        return TelegramWebhookResponse(ok=True, message="OK")


async def process_message(message: dict, trace_id: uuid.UUID) -> None:
    chat_id = message.get("chat", {}).get("id")
    text = message.get("text", "")
    username = message.get("from", {}).get("username", "unknown")

    logger.info(
        "telegram_message_received",
        trace_id=trace_id,
        chat_id=chat_id,
        text=text[:100] if text else None,
    )

    if text.startswith("/"):
        await handle_command(chat_id, text, trace_id)
    elif text.startswith("http"):
        await handle_url(chat_id, text, trace_id)
    else:
        await send_help_message(chat_id, trace_id)


async def handle_command(chat_id: str, command: str, trace_id: uuid.UUID) -> None:
    if command == "/start":
        logger.info("user_started_bot", trace_id=trace_id, chat_id=chat_id)
    elif command == "/list":
        logger.info("user_requested_list", trace_id=trace_id, chat_id=chat_id)
    elif command == "/help":
        logger.info("user_requested_help", trace_id=trace_id, chat_id=chat_id)
    else:
        logger.info("unknown_command", trace_id=trace_id, chat_id=chat_id, command=command)


async def handle_url(chat_id: str, url: str, trace_id: uuid.UUID) -> None:
    logger.info("url_submitted", trace_id=trace_id, chat_id=chat_id, url_length=len(url))


async def send_help_message(chat_id: str, trace_id: uuid.UUID) -> None:
    logger.info("help_requested", trace_id=trace_id, chat_id=chat_id)


async def process_callback_query(callback_query: dict, trace_id: uuid.UUID) -> None:
    pass
