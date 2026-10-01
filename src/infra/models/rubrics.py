from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.db.base import Base

if TYPE_CHECKING:
    from src.infra.models.documents import Document


class Rubric(Base):
    """Map shared rubric identifiers."""
    __tablename__ = "rubrics"

    code: Mapped[str] = mapped_column(nullable=False, primary_key=True)

    documents: Mapped[list[Document]] = relationship(
        secondary="document_rubrics",
        back_populates="rubrics",
        passive_deletes=True
    )
