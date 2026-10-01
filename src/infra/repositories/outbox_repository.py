from datetime import UTC, datetime, timedelta

from sqlalchemy import func, or_, select
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

    async def claim_pending(self) -> ProcessedOutboxEvent | None:
        """Claim a due event without waiting on another worker's row lock."""
        statement = (
            select(TransactionalOutbox)
            .where(
                TransactionalOutbox.processed_at.is_(None),
                or_(TransactionalOutbox.next_attempt_at.is_(None),
                    TransactionalOutbox.next_attempt_at <= func.now()),
            )
            .order_by(TransactionalOutbox.id)
            .limit(1)
            .with_for_update(skip_locked=True)
        )
        event = await self._session.scalar(statement)
        if event is None:
            return None
        return ProcessedOutboxEvent(id=event.id, document_id=event.document_id,
                                    operation=event.operation, attempts=event.attempts)

    async def mark_failed(self, event: ProcessedOutboxEvent, delay: float) -> None:
        """Persist retry timing; the caller commits it with the event lock held."""
        row = await self._session.get(TransactionalOutbox, event.id)
        if row is None:
            raise RuntimeError("Claimed outbox event disappeared.")
        row.attempts += 1
        row.next_attempt_at = datetime.now(UTC) + timedelta(seconds=delay)
