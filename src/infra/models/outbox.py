from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime
from sqlalchemy.orm import Mapped, mapped_column

from src.db.base import Base


class TransactionalOutbox(Base):
    __tablename__ = "transactional_outboxes"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    operation: Mapped[str] = mapped_column(nullable=False)
    document_id: Mapped[UUID] = mapped_column(nullable=False)
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
