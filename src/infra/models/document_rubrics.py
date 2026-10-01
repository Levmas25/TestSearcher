from uuid import UUID

from sqlalchemy import ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from src.db.base import Base


class DocumentRubric(Base):
    __tablename__ = "document_rubrics"

    document_id: Mapped[UUID] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"), primary_key=True)
    rubric_code: Mapped[str] = mapped_column(ForeignKey("rubrics.code", ondelete="CASCADE"), primary_key=True) 