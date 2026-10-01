from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query

from src.api.dependencies import get_document_service
from src.api.schemas import DeletionAccepted, DocumentGet, ErrorResponse
from src.application.service import DocumentService

router = APIRouter(prefix="/documents", tags=["documents"], responses={
    422: {"model": ErrorResponse, "description": "Invalid request"},
    503: {"model": ErrorResponse, "description": "Dependency unavailable"},
    500: {"model": ErrorResponse, "description": "Unexpected failure"},
})
Service = Annotated[DocumentService, Depends(get_document_service)]


@router.get("/search", response_model=list[DocumentGet])
async def search_documents(
    service: Service,
    q: Annotated[str, Query(min_length=1, pattern=r"\S")],
    limit: Annotated[int, Query(ge=1, le=20)] = 20,
) -> list[DocumentGet]:
    """Return matching documents ordered newest first."""
    documents = await service.get_documents(q.strip(), limit=limit)
    return [DocumentGet.model_validate(document) for document in documents]


@router.delete("/{document_id}", status_code=202, response_model=DeletionAccepted)
async def delete_document(document_id: UUID, service: Service) -> DeletionAccepted:
    """Commit SQL deletion and queue asynchronous search-index cleanup."""
    await service.delete(document_id)
    return DeletionAccepted(document_id=document_id)
