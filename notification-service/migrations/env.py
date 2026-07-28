import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy import Connection, pool, text
from sqlalchemy.ext.asyncio import async_engine_from_config

from notification_service.core.config import get_settings
from notification_service.models import NOTIFICATIONS_SCHEMA, Base

config = context.config
if config.config_file_name:
    fileConfig(config.config_file_name)

settings = get_settings()
config.set_main_option("sqlalchemy.url", settings.database_url)
target_metadata = Base.metadata


def configure(connection: Connection | None = None) -> None:
    context.configure(
        connection=connection,
        url=None if connection else settings.database_url,
        target_metadata=target_metadata,
        include_schemas=True,
        version_table_schema=NOTIFICATIONS_SCHEMA,
        literal_binds=connection is None,
        compare_type=True,
    )


def run_online_migrations(connection: Connection) -> None:
    configure(connection)
    with context.begin_transaction():
        context.run_migrations()


async def online() -> None:
    engine = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    async with engine.connect() as connection:
        await connection.execute(text(f'CREATE SCHEMA IF NOT EXISTS "{NOTIFICATIONS_SCHEMA}"'))
        await connection.commit()
        await connection.run_sync(run_online_migrations)
    await engine.dispose()


if context.is_offline_mode():
    configure()
    context.execute(f'CREATE SCHEMA IF NOT EXISTS "{NOTIFICATIONS_SCHEMA}"')
    with context.begin_transaction():
        context.run_migrations()
else:
    asyncio.run(online())
