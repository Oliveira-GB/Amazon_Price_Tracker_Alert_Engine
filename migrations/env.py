import os
from logging.config import fileConfig

from dotenv import load_dotenv
from sqlalchemy import pool
from sqlalchemy import create_engine
from sqlalchemy.engine import Connection

from alembic import context

load_dotenv()

from models.base import Base
from models.user import User
from models.product import Product
from models.user_product import UserProduct
from models.price_history import PriceHistory

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

alembic_url = config.get_main_option("sqlalchemy.url")
needs_override = (
    not alembic_url
    or alembic_url == "driver://user:pass@localhost/dbname"
    or alembic_url.startswith("postgresql+asyncpg")
)
if needs_override:
    database_url = os.environ.get("DATABASE_URL", "")
    if database_url.startswith("postgresql+asyncpg://"):
        alembic_url = "postgresql://" + database_url.replace("postgresql+asyncpg://", "")
    else:
        alembic_url = database_url
    config.set_main_option("sqlalchemy.url", alembic_url)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = create_engine(
        config.get_main_option("sqlalchemy.url"),
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
