from collections.abc import AsyncGenerator
from functools import cache

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.db.engine import get_async_engine



@cache
def get_sessionmaker() -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(
        get_async_engine(),
        class_=AsyncSession,
        expire_on_commit=False,
        autoflush=False,
        autocommit=False
    )


async def get_async_session() -> AsyncGenerator[AsyncSession, None]:
    async with get_sessionmaker()() as session:
        yield session