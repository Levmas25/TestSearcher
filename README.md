# TestSearcher

A Python document-search API using PostgreSQL, Elasticsearch, and a transactional
outbox for eventual search-index deletion.

## Run with Docker

Install Docker Desktop (Linux containers) and start its engine. Allow at least
4 GB of memory for the stack. From the project directory:

```sh
docker compose up --build -d --wait
```

Optionally copy `.env.example` to `.env` and adjust ports or local credentials
before starting. Compose passes these settings into the containers; the Python
settings classes do not read `.env` directly.

- API and Swagger UI: http://localhost:8000/docs
- OpenAPI: http://localhost:8000/openapi.json (also exported in `docs.json`)
- PostgreSQL: localhost:5432
- Elasticsearch: http://localhost:9200

The default PostgreSQL database/user is `testsearcher`, with password
`local-development-only`. Elasticsearch authentication is disabled for this local
setup. All published ports bind to loopback. This configuration is for development,
not public deployment.

The API waits for PostgreSQL and Elasticsearch health checks before starting. Its
own health check only checks that the HTTP application is serving OpenAPI; it does
not claim that schemas, search indexes, or imported documents exist.

**Current checkpoint:** the containers provide the API and backing services.
Database migrations, index initialization, CSV import, and the outbox worker are
not implemented yet. A fresh stack therefore serves `/docs`, but document
operations require schema/index initialization before they can work. Deletion
queues cleanup; without a worker, Elasticsearch entries are not removed yet.

```sh
docker compose logs -f api
docker compose ps
docker compose down
```

Named volumes retain data after `docker compose down`. PostgreSQL 18 uses the
`/var/lib/postgresql` volume mount. Changing initial PostgreSQL credentials in
`.env` does not update a database already initialized in an existing volume.

To run only the dependencies while developing the API locally:

```sh
docker compose up -d --wait postgres elasticsearch
uv sync
uv run uvicorn src.main:app --reload
```

For a local API process set `DB_USERNAME`, `DB_PASSWORD`, `DB_NAME`, `DB_HOST`, and
`DB_PORT` in its environment. Use localhost for DB_HOST and ELASTIC_HOST; inside
Compose the hostnames are `postgres` and `elasticsearch`. Elasticsearch defaults
to localhost:9200 and index `documents` outside Compose.

## API

- `GET /documents/search?q=python&limit=20`: up to 20 relevant search matches,
  fetched from SQL and ordered by creation time descending and ID ascending.
- `DELETE /documents/{uuid}`: 202 with `document_id` and
  `status: deletion_queued` after SQL deletion and outbox insertion commit.

Errors use `{"error": {"code": "...", "message": "...", "details": []}}`.
Validation errors return 422, unknown routes 404, unsupported methods 405,
dependency outages 503, and unexpected failures a generic 500. Internal failures
are logged, not returned to clients.

## Tests

Requires Python 3.14+ and uv:

```sh
uv sync
uv run python -m unittest discover -s tests -v
```

API tests use dependency overrides and mocks; they do not require running services
and do not replace live PostgreSQL/Elasticsearch integration tests.
