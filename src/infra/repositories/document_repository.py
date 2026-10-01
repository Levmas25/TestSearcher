from collections.abc import Sequence
from uuid import UUID

from sqlalchemy.ext.asyncio.session import AsyncSession
from sqlalchemy.orm.strategy_options import selectinload
from sqlalchemy.sql.expression import delete, select

from src.infra.models.documents import Document


class DocumentRepo:
    """Repository class for `documents` table"""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def delete(self, document_id: UUID) -> bool:
        stmt = delete(Document).where(Document.id == document_id)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none() is not None

    async def get_documents(self, document_ids: Sequence[UUID]) -> Sequence[Document]:
        """Returns all documents with ids in `document_ids`"""
        stmt = self._base_select().where(Document.id.in_(document_ids))
        result = await self._session.scalars(stmt)
        return list(result.all())

    def _base_select(self):
        """Base select statement for this repository that incldue selecinload with rubrics."""
        return select(Document).options(selectinload(Document.rubrics))