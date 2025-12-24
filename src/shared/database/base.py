"""SQLAlchemy base configuration.

Spec Reference: specs/08-integration-matrix.md Section 6.1
"""

from sqlalchemy.ext.asyncio import AsyncAttrs, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase


class Base(AsyncAttrs, DeclarativeBase):
    """Base class for all SQLAlchemy models."""

    pass


def create_engine(database_url: str, echo: bool = False):
    """Create async database engine.

    Args:
        database_url: PostgreSQL connection string (asyncpg format)
        echo: Enable SQL logging
    """
    return create_async_engine(database_url, echo=echo)


def create_session_factory(engine):
    """Create async session factory."""
    return async_sessionmaker(engine, expire_on_commit=False)
