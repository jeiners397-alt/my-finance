from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from app.config import get_settings

settings = get_settings()
engine = create_async_engine(
    settings.database_url.get_secret_value(),
    pool_pre_ping=True,
    pool_size=settings.db_pool_size,
    max_overflow=settings.db_max_overflow,
    pool_timeout=30,
    pool_recycle=1800,
    connect_args={
        "server_settings": {
            "timezone": "UTC",
            "statement_timeout": str(settings.db_statement_timeout_ms),
            "application_name": "my-finance",
        }
    },
)
SessionFactory = async_sessionmaker(engine, expire_on_commit=False, autoflush=False)


async def get_session():
    async with SessionFactory() as session:
        yield session
