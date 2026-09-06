from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    RABBITMQ_URI: str = "amqp://guest:guest@localhost:5672/"
    TG_BOT_TOKEN: str = ""
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/tracker"
    REDIS_URL: str = "redis://localhost:6379/0"
    ADMIN_TELEGRAM_ID: str = ""
    MAX_USER_QUOTA: int = 50
    SCRAPE_INTERVAL_HOURS: int = 6
    APP_ENV: str = "development"
    LOG_LEVEL: str = "INFO"

    SCRAPE_TIMEOUT_SECONDS: float = 10.0
    CIRCUIT_BREAKER_THRESHOLD: int = 5
    CIRCUIT_BREAKER_TIMEOUT_SECONDS: int = 120
    MAX_RETRIES: int = 3
    DLQ_MESSAGE_TTL_DAYS: int = 7
    ALERT_COOLDOWN_HOURS: int = 12

    RABBITMQ_PREFETCH_COUNT: int = 10
    DB_POOL_SIZE: int = 10
    DB_MAX_OVERFLOW: int = 20


settings = Settings()
