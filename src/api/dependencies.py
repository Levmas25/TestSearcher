from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from src.application.service import DocumentService
from src.db.session import get_async_session
from src.infra.unit_of_work import UnitOfWork


def get_document_service(
    request: Request,
    session: Annotated[AsyncSession, Depends(get_async_session)],
) -> DocumentService:
    return DocumentService(UnitOfWork(session), request.app.state.document_search)  # pyright: ignore[reportArgumentType]
