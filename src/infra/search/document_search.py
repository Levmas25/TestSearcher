from collections.abc import Iterator
from contextlib import contextmanager
from types import TracebackType
from typing import Self
from uuid import UUID

from elastic_transport import ConnectionError, ConnectionTimeout
from elasticsearch import ApiError, AsyncElasticsearch, NotFoundError

from src.application.exceptions import DependencyUnavailable


@contextmanager
def translate_search_errors() -> Iterator[None]:
    try:
        yield
    except (ConnectionError, ConnectionTimeout) as exc:
        raise DependencyUnavailable("Search unavailable.") from exc
    except ApiError as exc:
        if exc.status_code in (429, 502, 503, 504):
            raise DependencyUnavailable("Search unavailable.") from exc
        raise


class ElasticsearchDocumentSearch:
    def __init__(self, url: str, index: str = "documents") -> None:
        self._url = url
        self._index = index
        self._client: AsyncElasticsearch | None = None

    async def search_documents(
        self, query: str, *, limit: int = 20
    ) -> list[UUID]:
        with translate_search_errors():
            response = await self._active_client.search(
                index=self._index,
                query={"match": {"text": query}},
                size=limit,
            )
        return [UUID(hit["_id"]) for hit in response["hits"]["hits"]]

    async def delete(self, document_id: UUID) -> None:
        """Delete an indexed document; tolerate an already-absent document."""
        with translate_search_errors():
            try:
                await self._active_client.delete(
                    index=self._index,
                    id=str(document_id),
                )
            except NotFoundError as exc:
                # A missing index is a configuration failure, not a completed deletion.
                if not isinstance(exc.body, dict) or exc.body.get("result") != "not_found":
                    raise

    async def __aenter__(self) -> Self:
        if self._client is not None:
            raise RuntimeError("Search client is already initialized.")

        self._client = AsyncElasticsearch(self._url)
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        try:
            if self._client is not None:
                await self._client.close()
        finally:
            self._client = None

    @property
    def _active_client(self) -> AsyncElasticsearch:
        if self._client is None:
            raise RuntimeError(
                "Use ElasticsearchDocumentSearch inside an async context."
            )
        return self._client
