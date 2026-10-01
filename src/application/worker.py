import logging
from collections.abc import Callable
from contextlib import AbstractAsyncContextManager

from src.application.ports import DocumentSearch, UnitOfWork

logger = logging.getLogger(__name__)


class DeletionWorker:
    """Deliver outbox deletions at least once, retaining failed work for retry."""

    def __init__(
        self,
        transaction_factory: Callable[[], AbstractAsyncContextManager[UnitOfWork]],
        searcher: DocumentSearch,
        retry_base: float = 2,
        retry_max: float = 300,
    ) -> None:
        self._transaction_factory = transaction_factory
        self._searcher = searcher
        self._retry_base = retry_base
        self._retry_max = retry_max

    async def run_once(self) -> bool:
        """Handle one eligible event; return False if no unlocked work is due."""
        async with self._transaction_factory() as work:
            event = await work.outbox_repo.claim_pending()
            if event is None:
                return False
            try:
                if event.operation != "delete":
                    raise ValueError(f"Unsupported outbox operation: {event.operation}")
                await self._searcher.delete(event.document_id)
            except Exception:
                # Cancellation is not swallowed: it rolls back and releases the lock.
                delay = min(self._retry_max, self._retry_base * 2 ** min(event.attempts, 20))
                logger.exception("Outbox event %s failed; retry in %.1fs", event.id, delay)
                await work.outbox_repo.mark_failed(event, delay)
            else:
                await work.outbox_repo.mark_processed(event)
                logger.info("Deleted search document for outbox event %s", event.id)
        return True
