"""Validate and import the assignment CSV into PostgreSQL and Elasticsearch."""
import argparse
import ast
import asyncio
import csv
import json
import logging
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from uuid import UUID, uuid5

from elasticsearch import AsyncElasticsearch
from elasticsearch.helpers import async_bulk
from sqlalchemy import inspect, select, text
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import create_async_engine

from src.core.config import get_elastic_settings, get_settings
from src.db.base import Base
from src.infra.models import (Document, DocumentRubric, Rubric,
                              TransactionalOutbox)

logger = logging.getLogger(__name__)
# Keep this namespace stable: it determines imported document identities.
IMPORT_NAMESPACE = UUID("8b779878-822c-43fd-8826-6f83d380fb92")
MAPPING = {"properties": {"id": {"type": "keyword"},
                          "text": {"type": "text", "analyzer": "russian"}}}


@dataclass(frozen=True)
class ImportDocument:
    id: UUID
    text: str
    created_date: datetime
    rubrics: tuple[str, ...]


def parse_csv(path: Path) -> list[ImportDocument]:
    """Validate the whole file and collapse identical rows into stable documents.

    Source timestamps have no timezone and are preserved as naive datetimes.
    Rubric order is not significant when calculating document identity.
    """
    documents = {}
    with path.open(encoding="utf-8-sig", newline="") as source:
        reader = csv.DictReader(source)
        if (reader.fieldnames is None or len(reader.fieldnames) != 3
                or set(reader.fieldnames) != {"text", "created_date", "rubrics"}):
            raise ValueError("CSV must contain text, created_date, and rubrics columns.")
        for row in reader:
            try:
                if None in row or any(value is None for value in row.values()):
                    raise ValueError("Wrong number of CSV fields.")
                body = row["text"]
                if not body.strip():
                    raise ValueError("Document text must not be blank.")
                created = datetime.fromisoformat(row["created_date"])
                if created.tzinfo is not None:
                    raise ValueError("Expected a timestamp without timezone, as in the source dataset.")
                labels = ast.literal_eval(row["rubrics"])
                if not isinstance(labels, list) or any(not isinstance(x, str) or not x.strip() for x in labels):
                    raise ValueError("Rubrics must be a list of nonblank strings.")
                rubrics = tuple(sorted(set(labels)))
                identity = json.dumps([body, created.isoformat(), rubrics], ensure_ascii=False)
                document_id = uuid5(IMPORT_NAMESPACE, identity)
                documents[document_id] = ImportDocument(document_id, body, created, rubrics)
            except (ValueError, SyntaxError, TypeError) as exc:
                raise ValueError(f"CSV line {reader.line_num}: {exc}") from exc
    return list(documents.values())


async def ensure_index(client: AsyncElasticsearch, index: str) -> None:
    if not await client.indices.exists(index=index):
        await client.indices.create(index=index, mappings=MAPPING)
        return
    mappings = await client.indices.get_mapping(index=index)
    for mapping in mappings.values():
        properties = mapping.get("mappings", {}).get("properties", {})
        if (properties.get("id", {}).get("type") != "keyword"
                or properties.get("text", {}).get("type") != "text"
                or properties.get("text", {}).get("analyzer") != "russian"):
            raise ValueError("Existing index mapping is incompatible; select a new ELASTIC_INDEX.")


async def import_documents(documents: list[ImportDocument], batch_size: int) -> None:
    engine = create_async_engine(get_settings().async_url)
    elastic = get_elastic_settings()
    try:
        async with engine.connect() as connection:
            # Session-level lock serializes importers across committed batches.
            locked = await connection.scalar(text("SELECT pg_try_advisory_lock(731490021)"))
            await connection.commit()
            if not locked:
                raise RuntimeError("Another CSV import is already running.")
            try:
                async with connection.begin():
                    await connection.run_sync(Base.metadata.create_all)
                    columns = await connection.run_sync(
                        lambda sync: {c["name"] for c in inspect(sync).get_columns("transactional_outboxes")})
                    if not {"attempts", "next_attempt_at"}.issubset(columns):
                        raise RuntimeError("Existing outbox schema needs a migration for attempts and next_attempt_at.")
                async with AsyncElasticsearch(elastic.async_url, request_timeout=30) as client:
                    await ensure_index(client, elastic.index)
                    indexed = skipped = 0
                    for offset in range(0, len(documents), batch_size):
                        batch = documents[offset:offset + batch_size]
                        async with connection.begin():
                            deleted = set((await connection.scalars(
                                select(TransactionalOutbox.document_id).where(
                                    TransactionalOutbox.operation == "delete",
                                    TransactionalOutbox.document_id.in_([d.id for d in batch]),
                                ))).all())
                            skipped += len(deleted)
                            batch = [d for d in batch if d.id not in deleted]
                            if batch:
                                codes = sorted({code for doc in batch for code in doc.rubrics})
                                if codes:
                                    await connection.execute(insert(Rubric).values(
                                        [{"code": code} for code in codes]).on_conflict_do_nothing())
                                await connection.execute(insert(Document).values([
                                    {"id": d.id, "text": d.text, "created_date": d.created_date} for d in batch
                                ]).on_conflict_do_nothing())
                                links = [{"document_id": d.id, "rubric_code": code}
                                         for d in batch for code in d.rubrics]
                                # Bound parameter counts even when a row has many rubrics.
                                for start in range(0, len(links), 1000):
                                    await connection.execute(insert(DocumentRubric).values(
                                        links[start:start + 1000]).on_conflict_do_nothing())
                        if not batch:
                            continue
                        successful, errors = await async_bulk(client, (
                            {"_op_type": "index", "_index": elastic.index, "_id": str(d.id),
                             "_source": {"id": str(d.id), "text": d.text}} for d in batch
                        ), chunk_size=batch_size, raise_on_error=False, max_retries=3)
                        if errors:
                            raise RuntimeError(f"{len(errors)} indexing operations failed; rerun the import to resume.")
                        indexed += successful
                        logger.info("Imported %s/%s rows; indexed %s, skipped deleted %s",
                                    min(offset + batch_size, len(documents)), len(documents), indexed, skipped)
                    await client.indices.refresh(index=elastic.index)
                    logger.info("Import complete: %s indexed, %s previously deleted skipped", indexed, skipped)
            finally:
                await connection.rollback()
                await connection.execute(text("SELECT pg_advisory_unlock(731490021)"))
                await connection.commit()
    finally:
        await engine.dispose()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", type=Path)
    parser.add_argument("--batch-size", type=int, default=250)
    parser.add_argument("--validate-only", action="store_true")
    args = parser.parse_args()
    if not 1 <= args.batch_size <= 1000:
        parser.error("--batch-size must be between 1 and 1000")
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    try:
        documents = parse_csv(args.path)
        logger.info("Validated %s unique documents", len(documents))
        if not args.validate_only:
            asyncio.run(import_documents(documents, args.batch_size))
    except Exception:
        logger.exception("Import failed")
        raise SystemExit(1)


if __name__ == "__main__":
    main()
