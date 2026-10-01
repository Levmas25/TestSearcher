from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from sqlalchemy.exc import InterfaceError, OperationalError, TimeoutError
from sqlalchemy.ext.asyncio import AsyncSession

from src.application.exceptions import DependencyUnavailable
from src.infra.repositories.document_repository import DocumentRepo
from src.infra.repositories.outbox_repository import OutboxRepo


class UnitOfWork:
    """Group repository operations using a caller-owned session."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self.document_repo = DocumentRepo(self._session)
        self.outbox_repo = OutboxRepo(self._session)


    @asynccontextmanager
    async def transaction(self) -> AsyncIterator[UnitOfWork]:
        """Commit on successful exit and roll back on an exception."""
        try:
            async with self._session.begin():
                yield self
        except (OperationalError, InterfaceError, TimeoutError, OSError) as exc:
            raise DependencyUnavailable("Database unavailable.") from exc
