from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID, uuid7

from sqlalchemy import DateTime, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.db.base import Base

if TYPE_CHECKING:
    from src.infra.models.rubrics import Rubric


class Document(Base):
    """Map stored documents and their rubric associations."""
    __tablename__ = "documents"

    id: Mapped[UUID] = mapped_column(default=uuid7, primary_key=True)
    text: Mapped[str] = mapped_column(Text(), nullable=False)
    created_date: Mapped[datetime] = mapped_column(DateTime(), nullable=False)

    rubrics: Mapped[list[Rubric]] = relationship(
        secondary="document_rubrics",
        back_populates="documents",
        passive_deletes=True
    )
