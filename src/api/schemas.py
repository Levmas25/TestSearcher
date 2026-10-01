from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class DocumentGet(BaseModel):

    id: UUID
    text: str
    created_date: datetime
    rubrics: tuple[str, ...]

    model_config = ConfigDict(
        extra="forbid",
        from_attributes=True
    )


class DeletionAccepted(BaseModel):
    document_id: UUID
    status: Literal["deletion_queued"] = "deletion_queued"


class ErrorDetail(BaseModel):
    field: str
    message: str


class ErrorBody(BaseModel):
    code: str
    message: str
    details: list[ErrorDetail] = Field(default_factory=list)


class ErrorResponse(BaseModel):
    error: ErrorBody
