from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.events import ProcessedOutboxEvent, RegisterOutboxEvent
from src.infra.models.outbox import TransactionalOutbox


class OutboxRepo:

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def mark_processed(self, event: ProcessedOutboxEvent) -> None:
        outbox = await self._session.get(TransactionalOutbox, event.id)
        # A missing event has nothing left to mark.
        if not outbox:
            return
        outbox.processed_at = datetime.now(UTC)


    async def register_event(self, event: RegisterOutboxEvent) -> None:
        outbox = TransactionalOutbox(
            document_id=event.document_id,
            operation=event.operation
        )
        self._session.add(outbox)
