import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from api.bot.client import TelegramBot
from api.bot.keyboards import confirmation_keyboard, product_list_keyboard
from api.bot.templates import (
    admin_upgrade_request_template,
    error_template,
    help_template,
    processing_template,
    product_list_template,
    product_paused_template,
    product_removed_template,
    product_resumed_template,
    quota_exceeded_template,
    start_template,
    upgrade_requested_template,
)
from core.config import settings
from core.database import async_session_factory
from core.logging import configure_logging
from models.user import User
from models.user_product import UserProduct
from schemas.commands import ItemValidationCommand
from typing import cast

logger = configure_logging("bot_handlers")


async def get_or_create_user(session: Any, chat_id: str) -> User:
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
    return cast(User, user)


async def get_user_subscription_count(session: Any, user_id: uuid.UUID) -> int:
    result = await session.execute(
        select(func.count()).select_from(UserProduct).where(
            UserProduct.user_id == user_id,
            UserProduct.is_active,
        )
    )
    return result.scalar() or 0


async def get_user_subscriptions(
    session: Any, user_id: uuid.UUID
) -> list[UserProduct]:
    result = await session.execute(
        select(UserProduct)
        .options(selectinload(UserProduct.product))
        .where(UserProduct.user_id == user_id)
        .order_by(UserProduct.created_at.desc())
    )
    return list(result.scalars().all())


async def handle_start(
    bot: TelegramBot, chat_id: str, trace_id: uuid.UUID
) -> None:
    async with async_session_factory() as session:
        await get_or_create_user(session, chat_id)
        await session.commit()

    await bot.send_message(chat_id, start_template())


async def handle_help(
    bot: TelegramBot, chat_id: str, trace_id: uuid.UUID
) -> None:
    await bot.send_message(chat_id, help_template())


async def handle_list(
    bot: TelegramBot,
    chat_id: str,
    trace_id: uuid.UUID,
    page: int = 1,
    edit_message_id: int | None = None,
) -> None:
    async with async_session_factory() as session:
        user = await get_or_create_user(session, chat_id)
        subscriptions = await get_user_subscriptions(session, user.id)
        await session.commit()

        text, total_pages = product_list_template(
            subscriptions, user.quota_limit, page
        )
        keyboard = product_list_keyboard(subscriptions, page)

        if edit_message_id:
            await bot.edit_message_text(
                chat_id=chat_id,
                message_id=edit_message_id,
                text=text,
                reply_markup=keyboard,
            )
        else:
            await bot.send_message(
                chat_id, text, reply_markup=keyboard
            )


async def handle_pause(
    bot: TelegramBot,
    chat_id: str,
    trace_id: uuid.UUID,
    product_idx: int | None = None,
) -> None:
    async with async_session_factory() as session:
        user = await get_or_create_user(session, chat_id)

        if product_idx is not None:
            subscriptions = await get_user_subscriptions(session, user.id)
            if 0 < product_idx <= len(subscriptions):
                sub = subscriptions[product_idx - 1]
                sub.is_active = not sub.is_active
                await session.commit()

                title = sub.product.title or sub.product.asin
                if sub.is_active:
                    msg = product_resumed_template(title)
                else:
                    msg = product_paused_template(title)

                await bot.send_message(chat_id, msg)
                return

        await bot.send_message(
            chat_id,
            "Use /list e clique em 'Pausar' no produto desejado.",
        )


async def handle_delete(
    bot: TelegramBot,
    chat_id: str,
    trace_id: uuid.UUID,
    product_idx: int | None = None,
) -> None:
    async with async_session_factory() as session:
        user = await get_or_create_user(session, chat_id)

        if product_idx is not None:
            subscriptions = await get_user_subscriptions(session, user.id)
            if 0 < product_idx <= len(subscriptions):
                sub = subscriptions[product_idx - 1]
                title = sub.product.title or sub.product.asin

                await session.delete(sub)
                await session.commit()

                await bot.send_message(chat_id, product_removed_template(title))
                return

        await bot.send_message(
            chat_id,
            "Use /list e clique em 'Excluir' no produto desejado.",
        )


async def handle_request_upgrade(
    bot: TelegramBot,
    chat_id: str,
    trace_id: uuid.UUID,
) -> None:
    async with async_session_factory() as session:
        user = await get_or_create_user(session, chat_id)
        count = await get_user_subscription_count(session, user.id)
        await session.commit()

    await bot.send_message(chat_id, upgrade_requested_template())

    if settings.ADMIN_TELEGRAM_ID:
        admin_msg = admin_upgrade_request_template(
            chat_id, count, user.quota_limit
        )
        await bot.send_message(settings.ADMIN_TELEGRAM_ID, admin_msg)


async def handle_url(
    bot: TelegramBot,
    chat_id: str,
    url: str,
    trace_id: uuid.UUID,
) -> None:
    from core.rabbitmq import QUEUE_NAMES, publish_message
    from core.utils import extract_price_from_text

    logger.info(
        "url_submitted",
        trace_id=str(trace_id),
        chat_id=chat_id,
        url_length=len(url),
    )

    target_price = extract_price_from_text(url)
    url_clean = url.split()[0] if " " in url else url

    async with async_session_factory() as session:
        user = await get_or_create_user(session, chat_id)
        count = await get_user_subscription_count(session, user.id)

        if count >= user.quota_limit:
            await bot.send_message(
                chat_id,
                quota_exceeded_template(user.quota_limit),
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

    await publish_message(
        message_body=command.model_dump_json().encode(),
        routing_key=QUEUE_NAMES["item_validation"],
        headers={
            "trace_id": str(trace_id),
            "timestamp": command.timestamp.isoformat(),
            "retry_count": 0,
        },
    )

    await bot.send_message(chat_id, processing_template())


async def handle_callback(
    bot: TelegramBot,
    callback_query: dict,
    trace_id: uuid.UUID,
) -> None:
    data = callback_query.get("data", "")
    callback_query_id = str(callback_query.get("id", ""))
    chat_id = str(callback_query.get("message", {}).get("chat", {}).get("id", ""))
    message_id = callback_query.get("message", {}).get("message_id")

    logger.info(
        "callback_received",
        trace_id=str(trace_id),
        chat_id=chat_id,
        data=data,
    )

    parts = data.split(":", 1)
    action = parts[0] if parts else ""
    payload = parts[1] if len(parts) > 1 else ""

    if action == "pause":
        await _handle_pause_callback(bot, chat_id, message_id, payload, callback_query_id)
    elif action == "delete":
        await _handle_delete_callback(bot, chat_id, message_id, payload, callback_query_id)
    elif action == "page":
        page = int(payload) if payload.isdigit() else 1
        await _handle_page_callback(bot, chat_id, message_id, page, callback_query_id)
    elif action == "confirm":
        await _handle_confirm_callback(bot, chat_id, message_id, payload, callback_query_id)
    elif action == "cancel":
        await bot.answer_callback_query(
            callback_query_id,
            text="Operação cancelada.",
            show_alert=False,
        )
    else:
        await bot.answer_callback_query(
            callback_query_id,
            text="Ação não reconhecida.",
            show_alert=True,
        )


async def _handle_pause_callback(
    bot: TelegramBot,
    chat_id: str,
    message_id: int | None,
    product_id: str,
    callback_query_id: str,
) -> None:
    if not product_id:
        await bot.answer_callback_query(
            callback_query_id,
            text="Erro: produto não encontrado.",
            show_alert=True,
        )
        return

    try:
        product_uuid = uuid.UUID(product_id)
    except ValueError:
        await bot.answer_callback_query(
            callback_query_id,
            text="Erro: ID inválido.",
            show_alert=True,
        )
        return

    async with async_session_factory() as session:
        result = await session.execute(
            select(UserProduct)
            .options(selectinload(UserProduct.product))
            .where(UserProduct.product_id == product_uuid)
        )
        sub = result.scalar_one_or_none()

        if not sub:
            await bot.answer_callback_query(
                callback_query_id,
                text="Produto não encontrado.",
                show_alert=True,
            )
            return

        sub.is_active = not sub.is_active
        await session.commit()

        title = sub.product.title or sub.product.asin
        if sub.is_active:
            msg = product_resumed_template(title)
        else:
            msg = product_paused_template(title)

    await bot.answer_callback_query(callback_query_id, text="Atualizado!", show_alert=False)
    if message_id:
        await bot.edit_message_text(
            chat_id=chat_id,
            message_id=message_id,
            text=msg,
        )


async def _handle_delete_callback(
    bot: TelegramBot,
    chat_id: str,
    message_id: int | None,
    product_id: str,
    callback_query_id: str,
) -> None:
    if not product_id:
        await bot.answer_callback_query(
            callback_query_id,
            text="Erro: produto não encontrado.",
            show_alert=True,
        )
        return

    try:
        product_uuid = uuid.UUID(product_id)
    except ValueError:
        await bot.answer_callback_query(
            callback_query_id,
            text="Erro: ID inválido.",
            show_alert=True,
        )
        return

    async with async_session_factory() as session:
        result = await session.execute(
            select(UserProduct)
            .options(selectinload(UserProduct.product))
            .where(UserProduct.product_id == product_uuid)
        )
        sub = result.scalar_one_or_none()

        if not sub:
            await bot.answer_callback_query(
                callback_query_id,
                text="Produto não encontrado.",
                show_alert=True,
            )
            return

        title = sub.product.title or sub.product.asin
        keyboard = confirmation_keyboard("delete", product_id)

    await bot.answer_callback_query(callback_query_id)
    if message_id:
        from api.bot.templates import confirmation_template
        await bot.edit_message_text(
            chat_id=chat_id,
            message_id=message_id,
            text=confirmation_template("excluir", title[:50]),
            reply_markup=keyboard,
        )


async def _handle_page_callback(
    bot: TelegramBot,
    chat_id: str,
    message_id: int | None,
    page: int,
    callback_query_id: str,
) -> None:
    await bot.answer_callback_query(callback_query_id)

    if message_id:
        await handle_list(
            bot, chat_id, uuid.uuid4(), page=page, edit_message_id=message_id
        )


async def _handle_confirm_callback(
    bot: TelegramBot,
    chat_id: str,
    message_id: int | None,
    payload: str,
    callback_query_id: str,
) -> None:
    parts = payload.split(":", 1)
    action = parts[0] if parts else ""
    item_id = parts[1] if len(parts) > 1 else ""

    if action == "delete" and item_id:
        try:
            product_uuid = uuid.UUID(item_id)
        except ValueError:
            await bot.answer_callback_query(
                callback_query_id,
                text="Erro: ID inválido.",
                show_alert=True,
            )
            return

        async with async_session_factory() as session:
            result = await session.execute(
                select(UserProduct)
                .options(selectinload(UserProduct.product))
                .where(UserProduct.product_id == product_uuid)
            )
            sub = result.scalar_one_or_none()

            if sub:
                title = sub.product.title or sub.product.asin
                await session.delete(sub)
                await session.commit()
                msg = product_removed_template(title)
            else:
                msg = error_template("Produto não encontrado.")

        await bot.answer_callback_query(
            callback_query_id,
            text="Produto removido!",
            show_alert=False,
        )
        if message_id:
            await bot.edit_message_text(
                chat_id=chat_id,
                message_id=message_id,
                text=msg,
            )
    else:
        await bot.answer_callback_query(
            callback_query_id,
            text="Ação não suportada.",
            show_alert=True,
        )
