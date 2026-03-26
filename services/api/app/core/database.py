"""
Async Database Configuration
SQLAlchemy async engine and session management
"""
from typing import AsyncGenerator

from sqlalchemy import MetaData, event
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.pool import NullPool, QueuePool

from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)

# Global engine and session factory
_engine: AsyncEngine | None = None
_async_session_factory: async_sessionmaker[AsyncSession] | None = None


# SQLAlchemy 2.0 declarative base
class Base(DeclarativeBase):
    """Base class for all ORM models"""

    # Naming convention for constraints
    metadata = MetaData(
        naming_convention={
            "ix": "ix_%(column_0_label)s",
            "uq": "uq_%(table_name)s_%(column_0_name)s",
            "ck": "ck_%(table_name)s_%(constraint_name)s",
            "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
            "pk": "pk_%(table_name)s",
        }
    )


def get_engine() -> AsyncEngine:
    """Get or create the async database engine"""
    global _engine

    if _engine is None:
        settings = get_settings()

        # Determine pool class based on environment
        pool_class = QueuePool if settings.is_production else NullPool

        # Build engine kwargs conditionally based on pool class
        engine_kwargs = {
            "echo": settings.DATABASE_ECHO,
            "poolclass": pool_class,
        }

        # Only add pool parameters if using a pooled connection
        if pool_class == QueuePool:
            engine_kwargs.update({
                "pool_size": settings.DATABASE_POOL_SIZE,
                "max_overflow": settings.DATABASE_MAX_OVERFLOW,
                "pool_pre_ping": True,  # Verify connections before using
                "pool_recycle": 3600,  # Recycle connections after 1 hour
            })

        _engine = create_async_engine(
            settings.DATABASE_URL,
            **engine_kwargs
        )

        # Log connection pool events in debug mode
        if settings.DEBUG:

            @event.listens_for(_engine.sync_engine, "connect")
            def receive_connect(dbapi_conn, connection_record):
                logger.debug("database.connect")

            @event.listens_for(_engine.sync_engine, "close")
            def receive_close(dbapi_conn, connection_record):
                logger.debug("database.close")

        logger.info(
            "database.engine_created",
            url=settings.DATABASE_URL.split("@")[1] if "@" in settings.DATABASE_URL else "***",
            pool_size=settings.DATABASE_POOL_SIZE,
        )

    return _engine


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    """Get or create the async session factory"""
    global _async_session_factory

    if _async_session_factory is None:
        engine = get_engine()
        _async_session_factory = async_sessionmaker(
            engine,
            class_=AsyncSession,
            expire_on_commit=False,
            autocommit=False,
            autoflush=False,
        )
        logger.info("database.session_factory_created")

    return _async_session_factory


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    FastAPI dependency for database sessions

    Usage:
        @app.get("/items")
        async def read_items(db: AsyncSession = Depends(get_db)):
            result = await db.execute(select(Item))
            return result.scalars().all()

    Yields:
        AsyncSession: Database session
    """
    session_factory = get_session_factory()
    async with session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def init_db() -> None:
    """
    Initialize database (create tables if they don't exist)

    Note: In production, use Alembic migrations instead
    """
    engine = get_engine()
    async with engine.begin() as conn:
        # Import all models to ensure they're registered
        from app import models  # noqa: F401

        # Create tables (use Alembic in production)
        await conn.run_sync(Base.metadata.create_all)

        logger.info("database.initialized")


async def close_db() -> None:
    """Close database connections"""
    global _engine, _async_session_factory

    if _engine is not None:
        await _engine.dispose()
        _engine = None
        _async_session_factory = None
        logger.info("database.closed")
