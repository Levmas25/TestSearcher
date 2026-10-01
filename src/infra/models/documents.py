from __future__ import annotations

from datetime import date
from typing import TYPE_CHECKING
from uuid import UUID, uuid7

from sqlalchemy import Date, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.db.base import Base

if TYPE_CHECKING:
    from src.infra.models.rubrics import Rubric


class Document(Base):
    """ORM class for `documents` table"""
    __tablename__ = "documents"

    id: Mapped[UUID] = mapped_column(default=uuid7, primary_key=True, index=True)
    text: Mapped[str] = mapped_column(Text(), nullable=False)
    create_date: Mapped[date] = mapped_column(Date(), nullable=False)

    rubrics: Mapped[list[Rubric]] = relationship(
        secondary="DocumentRubric",
        back_populates="documents",
        passive_deletes=True
    )
    