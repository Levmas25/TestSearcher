import unittest
from contextlib import asynccontextmanager
from datetime import datetime
from unittest.mock import AsyncMock, patch
from uuid import uuid4

from elastic_transport import ConnectionError
from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError

from src.api.dependencies import get_document_service
from src.application.exceptions import DependencyUnavailable
from src.domain.documents import DocumentDTO
from src.infra.search.document_search import ElasticsearchDocumentSearch
from src.infra.unit_of_work import UnitOfWork
from src.main import create_app


class ApiTests(unittest.TestCase):
    def setUp(self):
        self.app = create_app()
        self.service = AsyncMock()
        self.app.dependency_overrides[get_document_service] = lambda: self.service
        self.client = TestClient(self.app, raise_server_exceptions=False)

    def tearDown(self):
        self.client.close()

    def assert_error(self, response, status, code):
        self.assertEqual(response.status_code, status)
        body = response.json()
        self.assertEqual(set(body), {"error"})
        self.assertEqual(set(body["error"]), {"code", "message", "details"})
        self.assertEqual(body["error"]["code"], code)
        self.assertIsInstance(body["error"]["details"], list)

    def test_search_serializes_domain_documents(self):
        document_id = uuid4()
        self.service.get_documents.return_value = [DocumentDTO(
            document_id, " original ", datetime(2020, 1, 1), ("rubric",))]
        response = self.client.get("/documents/search", params={"q": " python ", "limit": 3})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()[0]["id"], str(document_id))
        self.assertEqual(response.json()[0]["text"], " original ")
        self.assertEqual(response.json()[0]["rubrics"], ["rubric"])
        self.service.get_documents.assert_awaited_once_with("python", limit=3)

    def test_empty_results(self):
        self.service.get_documents.return_value = []
        self.assertEqual(self.client.get("/documents/search?q=missing").json(), [])

    def test_validation(self):
        for params in ({}, {"q": " "}, {"q": ""}, {"q": "x", "limit": 0},
                       {"q": "x", "limit": 21}, {"q": "x", "limit": "bad"}):
            with self.subTest(params=params):
                self.assert_error(self.client.get("/documents/search", params=params), 422, "validation_error")
        self.assert_error(self.client.delete("/documents/not-a-uuid"), 422, "validation_error")
        self.service.get_documents.assert_not_awaited()
        self.service.delete.assert_not_awaited()

    def test_delete_is_accepted(self):
        document_id = uuid4()
        response = self.client.delete(f"/documents/{document_id}")
        self.assertEqual(response.status_code, 202)
        self.assertEqual(response.json(), {"document_id": str(document_id), "status": "deletion_queued"})
        self.service.delete.assert_awaited_once_with(document_id)

    def test_http_errors(self):
        self.assert_error(self.client.get("/missing"), 404, "not_found")
        response = self.client.post("/documents/search")
        self.assert_error(response, 405, "method_not_allowed")
        self.assertIn("GET", response.headers["allow"])

    def test_dependencies_and_unexpected_errors_do_not_leak_details(self):
        for exc, status, code in ((DependencyUnavailable("secret host"), 503, "dependency_unavailable"),
                                  (RuntimeError("secret password"), 500, "internal_error")):
            self.service.get_documents.side_effect = exc
            with self.assertLogs("src.api.errors"):
                response = self.client.get("/documents/search?q=python")
            self.assert_error(response, status, code)
            self.assertNotIn("secret", response.text)
        self.service.delete.side_effect = DependencyUnavailable("commit failed")
        with self.assertLogs("src.api.errors"):
            self.assert_error(self.client.delete(f"/documents/{uuid4()}"), 503, "dependency_unavailable")

    def test_openapi_error_schema(self):
        schema = self.client.get("/openapi.json").json()
        response = schema["paths"]["/documents/search"]["get"]["responses"]["422"]
        self.assertEqual(response["content"]["application/json"]["schema"]["$ref"],
                         "#/components/schemas/ErrorResponse")

    def test_lifespan_closes_shared_client(self):
        client = AsyncMock()
        with patch("src.infra.search.document_search.AsyncElasticsearch", return_value=client):
            with TestClient(self.app):
                self.assertIsNotNone(self.app.state.document_search)
            client.close.assert_awaited_once()


class InfrastructureErrorTests(unittest.IsolatedAsyncioTestCase):
    async def test_database_commit_failure_is_translated(self):
        class Session:
            @asynccontextmanager
            async def begin(self):
                yield
                raise OperationalError("COMMIT", {}, RuntimeError("offline"))

        with self.assertRaises(DependencyUnavailable) as caught:
            async with UnitOfWork(Session()).transaction():
                pass
        self.assertIsInstance(caught.exception.__cause__, OperationalError)

    async def test_search_connection_failure_is_translated(self):
        client = AsyncMock()
        client.search.side_effect = ConnectionError("unreachable")
        with patch("src.infra.search.document_search.AsyncElasticsearch", return_value=client):
            async with ElasticsearchDocumentSearch("http://localhost:9200") as search:
                with self.assertRaises(DependencyUnavailable) as caught:
                    await search.search_documents("python")
                self.assertIsInstance(caught.exception.__cause__, ConnectionError)


if __name__ == "__main__":
    unittest.main()
