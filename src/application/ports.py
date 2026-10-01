from collections.abc import Sequence
from contextlib import AbstractAsyncContextManager
from typing import Protocol
from uuid import UUID

from src.domain.documents import DocumentDTO
from src.domain.events import ProcessedOutboxEvent, RegisterOutboxEvent


class DocumentRepo(Protocol):
    """Define document persistence operations."""

    async def delete(self, document_id: UUID) -> None: ...

    async def get_documents(self, document_ids: Sequence[UUID]) -> Sequence[DocumentDTO]: ...


class OutboxRepo(Protocol):
    """Define operations for durable outbox events."""

    async def mark_processed(self, event: ProcessedOutboxEvent) -> None: ...

    async def register_event(self, event: RegisterOutboxEvent) -> None: ...


class DocumentSearch(Protocol):
    """Define document search and index deletion operations."""

    async def search_documents(self, query: str, *, limit: int) -> Sequence[UUID]: ...

    async def delete(self, document_id: UUID) -> None: ...


class UnitOfWork(Protocol):
    """Commit grouped repository operations, or roll them back on failure."""

    document_repo: DocumentRepo
    outbox_repo: OutboxRepo

    def transaction(self) -> AbstractAsyncContextManager["UnitOfWork"]: ...
