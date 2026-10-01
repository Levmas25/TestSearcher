from uuid import UUID

from src.application.ports import DocumentSearch, UnitOfWork
from src.domain.documents import DocumentDTO
from src.domain.events import RegisterOutboxEvent


class DocumentService:

    def __init__(self, uow: UnitOfWork, searcher: DocumentSearch) -> None:
        self.uow = uow
        self.searcher = searcher

    async def get_documents(self, q: str, *, limit: int = 20) -> list[DocumentDTO]:

        document_ids = await self.searcher.search_documents(q, limit=limit)
        if not document_ids:
            return []
        async with self.uow.transaction() as work:
            document_dtos = await work.document_repo.get_documents(document_ids=document_ids)
        return list(document_dtos)

    async def delete(self, document_id: UUID) -> None:

        async with self.uow.transaction() as work:
            await work.document_repo.delete(document_id)
            await work.outbox_repo.register_event(RegisterOutboxEvent(document_id=document_id, operation="delete"))
