from types import TracebackType
from typing import Self
from uuid import UUID

from elasticsearch import AsyncElasticsearch, NotFoundError


class ElasticsearchDocumentSearch:
    def __init__(self, url: str, index: str = "documents") -> None:
        self._url = url
        self._index = index
        self._client: AsyncElasticsearch | None = None

    async def search_documents(
        self, query: str, *, limit: int = 20
    ) -> list[UUID]:
        response = await self._active_client.search(
            index=self._index,
            query={"match": {"text": query}},
            size=limit,
        )
        return [UUID(hit["_id"]) for hit in response["hits"]["hits"]]

    async def delete(self, document_id: UUID) -> None:
        """Delete an indexed document; tolerate an already-absent document."""
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
