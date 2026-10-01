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

1. Download the [assignment CSV](https://disk.yandex.ru/d/UYooXd9q2yqTMQ) and save it as `posts.csv`. The file is excluded from Git and copied into the Docker image during the build.
2. Optionally copy `.env.example` to `.env` to override local credentials or exposed ports.
3. Start the application:

```sh
docker compose up --build -d
```

4. On the first run, wait for the API container to start, then import the data:

```sh
docker compose exec api python -m src.import_csv posts.csv
```

The import creates missing tables and the Elasticsearch index. Run it before using
the document endpoints. Data persists in Docker volumes, so ordinary restarts do
not require another import. The worker retries automatically until initialization
is complete.

Default addresses:

| Service | Address |
| --- | --- |
| API | http://localhost:8000 |
| Swagger UI | http://localhost:8000/docs |
| PostgreSQL | localhost:5432 |
| Elasticsearch | http://localhost:9200 |

## Environment variables

Set container variables directly in the `environment` sections of
`docker-compose.yml`, or copy `.env.example` to `.env` in the project root and
adjust its values. Compose reads `.env` automatically and substitutes the
`${VARIABLE:-default}` values used in the Compose file.

For example:

```dotenv
POSTGRES_USER=testsearcher
POSTGRES_PASSWORD=your_password
POSTGRES_DB=testsearcher
API_PORT=8000
ELASTIC_PORT=9200
ELASTIC_INDEX=documents
```

The Compose file maps `POSTGRES_*` values to the API and worker's `DB_*` settings.
Keep their internal hosts as `postgres` and `elasticsearch`; published host ports
can be changed in `.env`. Re-run `docker compose up -d` after changing settings.

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

## Project layout

```text
src/
|-- api/                 # Routes, schemas, dependencies, exception handlers
|-- application/         # Service, worker logic, interfaces, exceptions
|-- domain/              # Document and event dataclasses
|-- core/                # Environment configuration
|-- db/                  # Engine, sessions, declarative base
|-- infra/
|   |-- models/          # SQLAlchemy models
|   |-- repositories/    # Document and outbox repositories
|   |-- search/          # Elasticsearch adapter
|   `-- unit_of_work.py  # Transaction management
|-- main.py              # API entry point and health endpoint
|-- worker.py            # Deletion worker entry point
`-- import_csv.py        # CSV import and database/index initialization
Dockerfile
docker-compose.yml
.env.example
docs.json                # Exported OpenAPI specification
pyproject.toml
uv.lock
posts.csv                # Downloaded input data (not tracked in Git)
```

## Local development

For local Python execution, install Python 3.14+ and uv:

```sh
uv sync
uv run python -m src.import_csv posts.csv --validate-only
uv run python -m src.import_csv posts.csv
uv run uvicorn src.main:app --reload
uv run python -m src.worker
```

Run the API and worker in separate terminals. Set `DB_USERNAME`, `DB_PASSWORD`, `DB_NAME`, `DB_HOST`, and `DB_PORT` in the process environment. Optional Elasticsearch settings are `ELASTIC_HOST`, `ELASTIC_PORT`, and `ELASTIC_INDEX` (defaults: localhost, 9200, documents). `.env` is read by Compose, not automatically by the local Python processes. Worker settings use `WORKER_POLL_INTERVAL`, `WORKER_RETRY_BASE`, and `WORKER_RETRY_MAX` (defaults: 2, 2, 300 seconds).
