from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class DocumentGet(BaseModel):

    id: UUID
    text: str
    created_date: datetime
    rubrics: tuple[str, ...]

    model_config = ConfigDict(
        extra="forbid",
        from_attributes=True
    )
