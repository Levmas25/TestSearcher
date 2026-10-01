from dataclasses import dataclass
from uuid import UUID


@dataclass
class RegisterOutboxEvent:

    operation: str
    document_id: UUID


@dataclass
class ProcessedOutboxEvent(RegisterOutboxEvent):

    id: int
    attempts: int = 0
