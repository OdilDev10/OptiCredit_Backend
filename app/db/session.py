"""Database session management."""

from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

from app.config import settings
from app.db.schema_compat import apply_schema_compat_fixes

# Create async engine
engine = create_async_engine(
    settings.database_url,
    echo=settings.environment == "development",
    future=True,
    pool_pre_ping=True,
)

# Create async session factory
AsyncSessionFactory = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Get database session for dependency injection."""
    async with AsyncSessionFactory() as session:
        try:
            yield session
        finally:
            await session.close()


async def init_db() -> None:
    """Initialize database (create tables and apply backward-compatible fixes)."""
    from app.db.base import Base

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await apply_schema_compat_fixes(conn)


async def close_db() -> None:
    """Close database connection."""
    await engine.dispose()
