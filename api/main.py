from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI
from fastapi.responses import JSONResponse

from api.routes import webhook
from core.config import settings
from core.database import engine
from core.logging import configure_logging
from core.rabbitmq import close_rabbitmq, init_rabbitmq

logger: structlog.BoundLogger | None = None


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    global logger
    logger = configure_logging("api")

    logger.info("application_starting", env=settings.APP_ENV)

    await init_rabbitmq()
    logger.info("rabbitmq_initialized")

    async with engine.begin() as conn:
        await conn.run_sync(lambda _: None)

    yield

    await close_rabbitmq()
    logger.info("application_shutdown")


app = FastAPI(
    title="Amazon Price Tracker API",
    description="Telegram Gateway for Amazon Price Tracker & Alert Engine",
    version="0.1.0",
    lifespan=lifespan,
)

app.include_router(webhook.router, prefix="/api/v1", tags=["webhook"])


@app.get("/health")
async def health_check() -> JSONResponse:
    return JSONResponse({"status": "healthy", "env": settings.APP_ENV})


@app.get("/ready")
async def readiness_check() -> JSONResponse:
    return JSONResponse({"status": "ready"})


def run() -> None:
    import uvicorn
    uvicorn.run(
        "api.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.APP_ENV == "development",
        log_level=settings.LOG_LEVEL.lower(),
    )


if __name__ == "__main__":
    run()
