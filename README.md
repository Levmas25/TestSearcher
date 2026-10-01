# TestSearcher

Work-in-progress document search API using PostgreSQL and Elasticsearch.

## Development

Requires Python 3.14+ and uv.

```sh
uv sync
uv run python -m unittest discover -s tests -v
```

Tests use in-memory SQLite for transaction behavior and mocked Elasticsearch
responses. They do not verify live PostgreSQL or Elasticsearch integration.

## Current design

- SQL repositories return immutable document DTOs with eagerly loaded rubrics.
- Search selects up to 20 relevant Elasticsearch matches by default, then loads
  existing SQL documents ordered by creation time descending and ID ascending.
- Deletion records an outbox event and deletes the document in one SQL transaction.
  Foreign-key cascades remove document/rubric links while preserving shared rubrics.
- The unit of work commits on successful exit and rolls back on exceptions. Its
  caller owns the session lifetime; use a fresh session per request/task.
- The Elasticsearch adapter owns a reusable async client. Its context should span
  the application lifespan. Repeated deletion of an absent document succeeds;
  a missing index remains an error.

Database settings currently come from environment variables: username, host,
port, name, password, and optional debug. Do not commit credentials.

## Still to implement

- FastAPI entry point, routes, dependencies, lifespan, and exception handlers.
- Alembic migrations and CSV import/index initialization.
- Outbox polling, retry handling, and worker lifecycle. Until a worker is added,
  SQL deletion only queues Elasticsearch cleanup; it does not perform it.
- Docker setup, live integration tests, and exported docs.json.
- An explicit timezone policy for CSV timestamps, which do not contain offsets.

The service currently treats deletion of a missing SQL document as idempotent
and still records a cleanup event. The eventual HTTP contract is not wired yet.
