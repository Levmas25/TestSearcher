from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import Select, delete, select
from sqlalchemy.ext.asyncio.session import AsyncSession
from sqlalchemy.orm.strategy_options import selectinload

from src.domain.documents import DocumentDTO
from src.infra.models.documents import Document


class DocumentRepo:
    """Load and delete documents without committing the transaction."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def delete(self, document_id: UUID) -> None:
        stmt = delete(Document).where(Document.id == document_id)
        await self._session.execute(stmt)


    async def get_documents(self, document_ids: Sequence[UUID]) -> Sequence[DocumentDTO]:
        """Return matching documents with rubrics, ordered newest first."""
        stmt = self._base_select().where(Document.id.in_(document_ids)).order_by(Document.created_date.desc(), Document.id.asc())
        result = await self._session.scalars(stmt)
        return [to_domain(model) for model in result.all()]

    def _base_select(self) -> Select[tuple[Document]]:
        """Build a document query that eagerly loads rubrics."""
        return select(Document).options(selectinload(Document.rubrics))


def to_domain(model: Document) -> DocumentDTO:
    return DocumentDTO(
        id=model.id,
        text=model.text,
        created_date=model.created_date,
        rubrics=tuple(rubric.code for rubric in model.rubrics)
    )
