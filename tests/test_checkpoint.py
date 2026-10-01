import unittest
from datetime import datetime
from unittest.mock import AsyncMock, patch
from uuid import uuid4

from elastic_transport import ApiResponseMeta, NodeConfig
from elasticsearch import NotFoundError
from sqlalchemy import event, func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.orm import configure_mappers

from src.api.schemas import DocumentGet
from src.application.service import DocumentService
from src.db.base import Base
from src.infra.models import (Document, DocumentRubric, Rubric,
                              TransactionalOutbox)
from src.infra.search.document_search import ElasticsearchDocumentSearch
from src.infra.unit_of_work import UnitOfWork


class TransactionTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        configure_mappers()
        self.engine = create_async_engine("sqlite+aiosqlite://")

        @event.listens_for(self.engine.sync_engine, "connect")
        def enable_foreign_keys(connection, _):
            connection.execute("PRAGMA foreign_keys=ON")

        async with self.engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        self.sessions = async_sessionmaker(self.engine, expire_on_commit=False)
        self.first_id, self.second_id = uuid4(), uuid4()
        async with self.sessions.begin() as session:
            rubric = Rubric(code="shared")
            session.add_all([
                Document(id=self.first_id, text="  original text  ",
                         created_date=datetime(2020, 1, 1), rubrics=[rubric]),
                Document(id=self.second_id, text="newer",
                         created_date=datetime(2021, 1, 1), rubrics=[rubric]),
            ])

    async def asyncTearDown(self):
        await self.engine.dispose()

    async def test_delete_commits_outbox_and_preserves_shared_rubric(self):
        search = AsyncMock()
        async with self.sessions() as session:
            await DocumentService(UnitOfWork(session), search).delete(self.first_id)
        search.delete.assert_not_awaited()
        async with self.sessions() as session:
            self.assertIsNone(await session.get(Document, self.first_id))
            self.assertIsNotNone(await session.get(Document, self.second_id))
            self.assertIsNotNone(await session.get(Rubric, "shared"))
            self.assertEqual(await session.scalar(select(func.count()).select_from(DocumentRubric)), 1)
            recorded = (await session.scalars(select(TransactionalOutbox))).one()
            self.assertEqual(recorded.document_id, self.first_id)
            self.assertIsNone(recorded.processed_at)

    async def test_failure_after_enqueue_rolls_back_both_writes(self):
        async with self.sessions() as session:
            uow = UnitOfWork(session)
            register = uow.outbox_repo.register_event

            async def fail_after_enqueue(event):
                await register(event)
                await session.flush()
                raise RuntimeError("simulated failure")

            with patch.object(uow.outbox_repo, "register_event", side_effect=fail_after_enqueue):
                with self.assertRaisesRegex(RuntimeError, "simulated failure"):
                    await DocumentService(uow, AsyncMock()).delete(self.first_id)
        async with self.sessions() as session:
            self.assertIsNotNone(await session.get(Document, self.first_id))
            self.assertEqual(await session.scalar(select(func.count()).select_from(TransactionalOutbox)), 0)
            self.assertEqual(await session.scalar(select(func.count()).select_from(DocumentRubric)), 2)

    async def test_search_returns_detached_dtos_in_date_order(self):
        search = AsyncMock()
        search.search_documents.return_value = [self.first_id, uuid4(), self.second_id]
        async with self.sessions() as session:
            documents = await DocumentService(UnitOfWork(session), search).get_documents("query")
        self.assertEqual([doc.id for doc in documents], [self.second_id, self.first_id])
        self.assertEqual(documents[1].rubrics, ("shared",))
        self.assertEqual(DocumentGet.model_validate(documents[1]).text, "  original text  ")


class SearchTests(unittest.IsolatedAsyncioTestCase):
    def missing(self, body):
        meta = ApiResponseMeta(404, "1.1", {}, 0, NodeConfig("http", "localhost", 9200))
        return NotFoundError("not found", meta, body)

    async def test_delete_tolerates_missing_document_but_not_missing_index(self):
        adapter = ElasticsearchDocumentSearch("http://localhost:9200")
        client = AsyncMock()
        with patch("src.infra.search.document_search.AsyncElasticsearch", return_value=client):
            async with adapter:
                client.delete.side_effect = self.missing({"result": "not_found"})
                await adapter.delete(uuid4())
                client.delete.side_effect = self.missing({"error": {"type": "index_not_found_exception"}})
                with self.assertRaises(NotFoundError):
                    await adapter.delete(uuid4())
        client.close.assert_awaited_once()
        with self.assertRaises(RuntimeError):
            await adapter.search_documents("query")

    async def test_search_converts_ids(self):
        document_id = uuid4()
        client = AsyncMock()
        client.search.return_value = {"hits": {"hits": [{"_id": str(document_id)}]}}
        with patch("src.infra.search.document_search.AsyncElasticsearch", return_value=client):
            async with ElasticsearchDocumentSearch("http://localhost:9200") as adapter:
                self.assertEqual(await adapter.search_documents("python"), [document_id])


if __name__ == "__main__":
    unittest.main()
