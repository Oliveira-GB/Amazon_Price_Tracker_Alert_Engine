import asyncio
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

import httpx

from core.config import settings
from core.logging import configure_logging

logger = configure_logging("telegram_bot")


@dataclass
class TelegramResponse:
    ok: bool
    result: dict | None = None
    error_code: int | None = None
    description: str | None = None


class CircuitBreakerOpen(Exception):
    pass


class TelegramBot:
    def __init__(self, token: str | None = None):
        self.token = token or settings.TG_BOT_TOKEN
        self.base_url = f"https://api.telegram.org/bot{self.token}"
        self._consecutive_failures = 0
        self._circuit_open_until: datetime | None = None

    async def _request(
        self,
        method: str,
        data: dict[str, Any] | None = None,
        retry_count: int = 0,
    ) -> TelegramResponse:
        if self._circuit_open_until:
            if datetime.now(UTC) < self._circuit_open_until:
                raise CircuitBreakerOpen(
                    f"Circuit breaker open until {self._circuit_open_until}"
                )
            self._circuit_open_until = None

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(
                    f"{self.base_url}/{method}",
                    json=data,
                )
                result = response.json()

                if result.get("ok"):
                    self._consecutive_failures = 0
                    return TelegramResponse(ok=True, result=result.get("result"))

                error_code = result.get("error_code")
                description = result.get("description", "")

                if error_code == 429:
                    retry_after = int(response.headers.get("Retry-After", 60))
                    logger.warning(
                        "telegram_rate_limited",
                        retry_after=retry_after,
                        retry_count=retry_count,
                    )
                    if retry_count < settings.MAX_RETRIES:
                        await asyncio.sleep(retry_after)
                        return await self._request(method, data, retry_count + 1)

                if error_code in (403, 401):
                    logger.error(
                        "telegram_auth_error",
                        error_code=error_code,
                        description=description,
                    )

                self._consecutive_failures += 1
                if self._consecutive_failures >= settings.CIRCUIT_BREAKER_THRESHOLD:
                    self._circuit_open_until = datetime.now(UTC)
                    wait_seconds = settings.CIRCUIT_BREAKER_TIMEOUT_SECONDS
                    logger.error(
                        "telegram_circuit_breaker_opened",
                        failures=self._consecutive_failures,
                        wait_seconds=wait_seconds,
                    )

                return TelegramResponse(
                    ok=False,
                    error_code=error_code,
                    description=description,
                )

        except httpx.TimeoutException as e:
            self._consecutive_failures += 1
            logger.error(
                "telegram_timeout",
                retry_count=retry_count,
                error=str(e),
            )
            if retry_count < settings.MAX_RETRIES:
                await asyncio.sleep(2 ** retry_count)
                return await self._request(method, data, retry_count + 1)
            raise

        except Exception as e:
            self._consecutive_failures += 1
            logger.error(
                "telegram_request_error",
                error=str(e),
                method=method,
            )
            raise

    async def send_message(
        self,
        chat_id: str,
        text: str,
        parse_mode: str = "Markdown",
        reply_markup: dict | None = None,
        disable_web_page_preview: bool = True,
    ) -> TelegramResponse:
        data: dict[str, Any] = {
            "chat_id": chat_id,
            "text": text,
            "parse_mode": parse_mode,
            "disable_web_page_preview": disable_web_page_preview,
        }
        if reply_markup:
            data["reply_markup"] = reply_markup

        return await self._request("sendMessage", data)

    async def edit_message_text(
        self,
        chat_id: str,
        message_id: int,
        text: str,
        parse_mode: str = "Markdown",
        reply_markup: dict | None = None,
    ) -> TelegramResponse:
        data: dict[str, Any] = {
            "chat_id": chat_id,
            "message_id": message_id,
            "text": text,
            "parse_mode": parse_mode,
        }
        if reply_markup:
            data["reply_markup"] = reply_markup

        return await self._request("editMessageText", data)

    async def answer_callback_query(
        self,
        callback_query_id: str,
        text: str | None = None,
        show_alert: bool = False,
    ) -> TelegramResponse:
        data: dict[str, Any] = {
            "callback_query_id": callback_query_id,
            "show_alert": show_alert,
        }
        if text:
            data["text"] = text

        return await self._request("answerCallbackQuery", data)

    async def delete_message(
        self,
        chat_id: str,
        message_id: int,
    ) -> TelegramResponse:
        data = {
            "chat_id": chat_id,
            "message_id": message_id,
        }
        return await self._request("deleteMessage", data)

    async def get_me(self) -> TelegramResponse:
        return await self._request("getMe")


_bot: TelegramBot | None = None


def get_telegram_bot() -> TelegramBot:
    global _bot
    if _bot is None:
        _bot = TelegramBot()
    return _bot
