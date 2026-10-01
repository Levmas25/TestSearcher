import asyncio
import logging
import signal
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from src.application.worker import DeletionWorker
from src.core.config import WorkerSettings, get_elastic_settings
from src.db.engine import dispose_engine
from src.db.session import get_sessionmaker
from src.infra.search.document_search import ElasticsearchDocumentSearch
from src.infra.unit_of_work import UnitOfWork

logger = logging.getLogger(__name__)


async def run() -> None:
    settings = WorkerSettings()
    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    previous_handlers = {}
    for sig in (signal.SIGINT, signal.SIGTERM):
        previous_handlers[sig] = signal.getsignal(sig)
        try:
            loop.add_signal_handler(sig, stop.set)
        except NotImplementedError:  # Windows development runs.
            signal.signal(sig, lambda *_: loop.call_soon_threadsafe(stop.set))

    try:
        sessions = get_sessionmaker()

        @asynccontextmanager
        async def transaction() -> AsyncIterator[UnitOfWork]:
            async with sessions() as session:
                async with UnitOfWork(session).transaction() as work:
                    yield work

        elastic = get_elastic_settings()
        async with ElasticsearchDocumentSearch(elastic.async_url, elastic.index) as search:
            worker = DeletionWorker(transaction, search, settings.retry_base, settings.retry_max)
            logger.info("Deletion worker started")
            while not stop.is_set():
                try:
                    if await worker.run_once():
                        continue
                except Exception:
                    logger.exception("Worker database iteration failed; will retry")
                try:
                    await asyncio.wait_for(stop.wait(), timeout=settings.poll_interval)
                except TimeoutError:
                    pass
    finally:
        await dispose_engine()
        get_sessionmaker.cache_clear()
        for sig, handler in previous_handlers.items():
            try:
                loop.remove_signal_handler(sig)
            except NotImplementedError:
                pass
            signal.signal(sig, handler)
        logger.info("Deletion worker stopped")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    asyncio.run(run())
