from collections.abc import AsyncGenerator
from typing import Annotated

from fastapi import Depends, Header, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import async_session_factory


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


DbSession = Annotated[AsyncSession, Depends(get_db_session)]


def verify_telegram_secret(
    x_telegram_bot_api_secret_token: str | None = Header(None),
) -> str:
    from core.config import settings

    if not settings.TG_BOT_TOKEN:
        return "dev"

    if x_telegram_bot_api_secret_token != settings.TG_BOT_TOKEN:
        raise HTTPException(status_code=403, detail="Invalid token")

    return x_telegram_bot_api_secret_token


TelegramSecret = Annotated[str, Depends(verify_telegram_secret)]
