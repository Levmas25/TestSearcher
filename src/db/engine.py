from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from src.core.config import get_settings

_ENGINE: AsyncEngine | None = None


def get_async_engine() -> AsyncEngine:
    global _ENGINE
    if _ENGINE is None:
        settings = get_settings()
        _ENGINE = create_async_engine(
            settings.async_url,
            pool_pre_ping=True,
            echo=settings.debug,
            pool_recycle=3600,
            connect_args={
                "server_settings":
                    {
                        "timezone": "UTC"
                    }
            }
        )
    return _ENGINE


async def dispose_engine() -> None:
    global _ENGINE
    if _ENGINE is not None:
        await _ENGINE.dispose()
        _ENGINE = None
    