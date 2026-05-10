"""Async SQLAlchemy engine + session factory.

`init_db()` is called once at startup; it creates tables from the ORM models if
they don't exist yet. For schema migrations beyond v1 we'll add Alembic.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from interrogation_pipeline.config.settings import settings
from interrogation_pipeline.store.models import Base


def _make_engine():
    url = f"sqlite+aiosqlite:///{settings.db_path.as_posix()}"
    return create_async_engine(
        url,
        echo=False,
        future=True,
        connect_args={"timeout": 30},
    )


engine = _make_engine()
SessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def init_db() -> None:
    """Create all tables and enable foreign keys."""
    async with engine.begin() as conn:
        await conn.exec_driver_sql("PRAGMA journal_mode=WAL")
        await conn.exec_driver_sql("PRAGMA foreign_keys=ON")
        await conn.run_sync(Base.metadata.create_all)


@asynccontextmanager
async def session_scope() -> AsyncIterator[AsyncSession]:
    """Context-managed async session with automatic commit/rollback."""
    async with SessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
