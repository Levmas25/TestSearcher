from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass(frozen=True, slots=True)
class DocumentDTO:
    """Represent a document independently of its persistence model."""
    id: UUID
    text: str
    created_date: datetime
    rubrics: tuple[str, ...]
