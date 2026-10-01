from contextlib import asynccontextmanager

from fastapi import FastAPI

from src.api.errors import register_exception_handlers
from src.api.routes import router
from src.core.config import get_elastic_settings
from src.db.engine import dispose_engine
from src.db.session import get_sessionmaker
from src.infra.search.document_search import ElasticsearchDocumentSearch


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_elastic_settings()
    try:
        async with ElasticsearchDocumentSearch(settings.async_url, settings.index) as search:
            app.state.document_search = search
            yield
    finally:
        await dispose_engine()
        get_sessionmaker.cache_clear()


def create_app() -> FastAPI:
    app = FastAPI(title="TestSearcher", version="0.1.0", lifespan=lifespan)
    register_exception_handlers(app)
    app.include_router(router)
    return app


app = create_app()
