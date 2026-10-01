# TestSearcher

Implementation of the [Python test assignment](https://invented-step-baf.notion.site/Python-36b12b6bba7647378eee6f13cb1e36ec): search document text through Elasticsearch and delete documents from PostgreSQL and the search index.

## Stack

- Python 3.14, FastAPI, Pydantic.
- PostgreSQL 18, SQLAlchemy asyncio, asyncpg.
- Elasticsearch 9.5.1 and its asynchronous Python client.
- Docker Compose; uv and `uv.lock` for dependencies.

PostgreSQL stores `id`, `text`, `created_date`, and rubric associations. Rubrics are normalized into `rubrics` and `document_rubrics` tables and returned as an array by the API. Elasticsearch stores `id` and `text`; the database UUID is also its document `_id`. Text uses the Russian analyzer.

## Setup

Requires Docker with Linux containers and Docker Compose. Run commands from the repository root.

1. Download the [assignment CSV](https://disk.yandex.ru/d/UYooXd9q2yqTMQ) and save it as `posts.csv`. The file is excluded from Git and the Docker image.
2. Optionally copy `.env.example` to `.env` to override local credentials or exposed ports.
3. Start the dependencies, initialize the data, then start the application:

```sh
docker compose up -d --wait postgres elasticsearch
docker compose stop api worker
docker compose build api
docker compose run --rm --no-deps --volume "${PWD}/posts.csv:/data/posts.csv:ro" api python -m src.import_csv /data/posts.csv
docker compose up --build -d --wait
```

The volume command works in PowerShell and POSIX shells. Stop if the importer fails; fix its reported error before starting the API and worker.

Default addresses:

| Service | Address |
| --- | --- |
| API | http://localhost:8000 |
| Swagger UI | http://localhost:8000/docs |
| PostgreSQL | localhost:5432 |
| Elasticsearch | http://localhost:9200 |

The default PostgreSQL database and user are `testsearcher`; the development password is `local-development-only`. Elasticsearch authentication is disabled for this local setup. Published ports bind to localhost.

```sh
docker compose logs -f api worker
docker compose ps
docker compose down
```

Named volumes preserve data when containers stop. The importer creates missing tables, but does not migrate existing schemas. An older outbox table must include `attempts` and `next_attempt_at` before running the current worker.

## API endpoints

### GET /documents/search

Query parameters:

- `q`: required, nonblank text query.
- `limit`: optional integer from 1 to 20; defaults to 20.

Returns `200` with an array of documents, each containing `id`, `text`, `created_date`, and `rubrics`. No matches returns `[]`.

```sh
curl "http://localhost:8000/documents/search?q=python&limit=20"
```

Search first selects up to 20 relevant Elasticsearch matches, then fetches existing PostgreSQL documents and sorts them by creation date descending, with ID ascending as a tie-breaker. This interprets the assignment as sorting the selected matches, rather than selecting the newest documents from all matches.

### DELETE /documents/{document_id}

Accepts a UUID. Returns `202 Accepted` after deleting the SQL document and writing its cleanup event in one transaction:

```json
{
  "document_id": "00000000-0000-0000-0000-000000000001",
  "status": "deletion_queued"
}
```

The worker removes the Elasticsearch entry asynchronously and retries failures. Repeated deletion is accepted. Shared rubrics are retained. Search results are fetched from PostgreSQL, so stale index entries do not return deleted SQL documents; they can temporarily reduce the result count.

### GET /health

Returns `200` with `{"status":"ok"}`. This is API liveness; backing-service health is checked separately by Compose.

### Errors

All API errors use the same envelope:

```json
{
  "error": {
    "code": "validation_error",
    "message": "Request validation failed.",
    "details": [{"field": "query.limit", "message": "Input should be less than or equal to 20"}]
  }
}
```

Statuses: `422` for invalid requests, `404` for unknown routes, `405` for unsupported methods, `503` for dependency outages, and `500` for unexpected failures. Non-validation errors have an empty `details` array; internal diagnostics are logged.

## OpenAPI

- Required exported specification: [docs.json](docs.json).
- Live specification: http://localhost:8000/openapi.json.
- Interactive documentation: http://localhost:8000/docs.

## Important files and scripts

| Location | Purpose |
| --- | --- |
| `src/main.py` | FastAPI application, lifespan, and health endpoint |
| `src/api/` | Routes, response schemas, dependencies, exception handlers |
| `src/application/service.py` | Search and deletion use cases |
| `src/application/worker.py` | Outbox deletion processing and retry policy |
| `src/worker.py` | Worker entry point and graceful shutdown |
| `src/import_csv.py` | CSV validation, database initialization, bulk indexing |
| `src/infra/models/` | SQLAlchemy tables |
| `src/infra/repositories/` | Document and outbox persistence |
| `src/infra/unit_of_work.py` | SQL transaction boundary |
| `src/infra/search/document_search.py` | Elasticsearch adapter |
| `src/core/config.py` | Environment settings |
| `Dockerfile`, `docker-compose.yml` | API, worker, PostgreSQL, Elasticsearch containers |

The importer preserves text and naive source timestamps, parses rubric lists with `ast.literal_eval`, and generates stable IDs. Exact duplicate rows collapse; the provided 1,964 rows produce 1,500 unique documents. Rerunning the same import is safe. IDs recorded in deletion events are skipped; retaining those events preserves this behavior. Run imports while API and worker are stopped.

For local Python execution, install Python 3.14+ and uv:

```sh
uv sync
uv run python -m src.import_csv posts.csv --validate-only
uv run python -m src.import_csv posts.csv
uv run uvicorn src.main:app --reload
uv run python -m src.worker
```

Run the API and worker in separate terminals. Set `DB_USERNAME`, `DB_PASSWORD`, `DB_NAME`, `DB_HOST`, and `DB_PORT` in the process environment. Optional Elasticsearch settings are `ELASTIC_HOST`, `ELASTIC_PORT`, and `ELASTIC_INDEX` (defaults: localhost, 9200, documents). `.env` is read by Compose, not automatically by the local Python processes. Worker settings use `WORKER_POLL_INTERVAL`, `WORKER_RETRY_BASE`, and `WORKER_RETRY_MAX` (defaults: 2, 2, 300 seconds).
