from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.config import get_settings

settings = get_settings()

engine = create_async_engine(settings.database_url, pool_pre_ping=True, future=True)
AsyncSessionLocal = async_sessionmaker(bind=engine, expire_on_commit=False, class_=AsyncSession)


class Base(DeclarativeBase):
    pass


async def get_db():
    async with AsyncSessionLocal() as session:
        yield session


async def init_models():
    """Create tables if they don't exist yet. Fine for first deploy; use
    Alembic migrations (backend/alembic/) for anything after that."""
    import app.models  # noqa: F401  (ensure models are registered on Base)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
