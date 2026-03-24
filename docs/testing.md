# Testing Guide

## Overview

The project uses **pytest** for all backend testing (and **pytest-asyncio** for asynchronous tests where necessary). Tests are split into three levels: unit, integration, and system. The frontend does not have any tests.

```
api/tests/
├── conftest.py                        # Shared fixtures, env setup
├── unit/
│   ├── conftest.py                    # TestClient fixture
│   ├── test_api_endpoints.py          # Health, autocomplete, chat, embed, generate
├── unit/
│   ├── conftest.py                    # TestClient fixture
│   ├── test_api_endpoints.py          # Health, autocomplete, chat, embed, generate
│   ├── test_connections_endpoint.py   # Connections router
│   ├── test_ai_router.py              # RAG helpers, similar publications
│   ├── scripts_tests/
│   │   └── test_enrich.py             # Enrichment pipeline
│   └── utils_tests/
│       ├── test_ai_utils.py           # AI service config, async requests
│       ├── test_schemas.py            # Pydantic schema validation
│       └── test_connections_utils.py  # Connections utility functions
├── integration/
│   └── test_integration_api.py        # End-to-end API tests
└── system/
    ├── test_smoke_dev.py              # Dev environment smoke tests
    └── test_smoke_deploy.py           # Production deployment smoke tests
```

## Running Tests

| Command               | What it runs                      | Requirements                      |
| --------------------- | --------------------------------- | --------------------------------- |
| `make test`           | Unit + integration tests          | Test image built automatically    |
| `make test-unit`      | Unit tests only                   | None (offline)                    |
| `make test-dev`       | Integration + dev smoke tests     | `make dev` running                |
| `make test-deploy`    | Production smoke tests            | Run on the production server      |

Tests run inside a container built from `api/Containerfile.test`, which extends the API dev image and adds pytest dependencies. The container uses host networking and mounts `api/` as read-only at `/work`.

## Test Levels

### Unit Tests

Located in `tests/unit/`. No external services needed — everything is mocked.

**What they cover:**

- **API endpoints** — health, autocomplete, chat, embed, generate, connections
- **Database utilities** — connection management, index creation, shutdown
- **Query utilities** — Lucene escaping, query building, input sanitization
- **AI utilities** — async HTTP requests, embedding calls, config loading
- **Schema validation** — Pydantic model validation and edge cases
- **Autocomplete logic** — search result processing
- **Connections** — graph traversal utility functions
- **Enrichment pipeline** — abstract fetching, embedding generation, Neo4j storage
- **RAG helpers** — similar publication retrieval, prompt building

### Integration Tests

Located in `tests/integration/`. Require the dev pod to be running (`make dev`). Tests skip gracefully if services are unavailable.

**What they cover:**

- Health, autocomplete, connections, generate, chat, and embed endpoints
- Actual HTTP request/response flow against the running API
- CORS header handling

### System Tests

Located in `tests/system/`. Two separate files for dev and production environments.

**Dev smoke tests** (`test_smoke_dev.py`) — verify the local dev setup:
- SSH tunnel connectivity
- Pod services running
- API reachable through tunnel
- Neo4j and Ollama connectivity

**Deploy smoke tests** (`test_smoke_deploy.py`) — verify production:
- Network ports open
- HTTP/HTTPS endpoints responding
- Neo4j and Ollama health checks

## Configuration

### Conftest Hierarchy

Three `conftest.py` files provide fixtures at different scopes:

1. **`api/conftest.py`** — custom pytest report headers and terminal summaries, enhanced error reporting
2. **`api/tests/conftest.py`** — sets required environment variables (Neo4j, AI service URLs), provides `mock_neo4j_driver()` fixture
3. **`api/tests/unit/conftest.py`** — provides `client()` fixture (FastAPI `TestClient`), mocks database startup/shutdown

## Testing Patterns

### Mocking

Unit tests mock all external dependencies:

- **Neo4j driver** — mocked with context manager support via `mock_neo4j_driver()` fixture
- **HTTP clients** — `AsyncMock` for external service calls (Ollama, OpenAlex)
- **Database functions** — patched at import time to isolate endpoint tests

## Test Dependencies

Required dependencies for testing are defined in `api/requirements-dev.txt`, which also uses the non-testing requirements found in `api/requirements.txt`.

## Frontend

The frontend has **no automated tests**. Code quality is enforced through:
- ESLint (`npm run lint`)
- TypeScript compilation (`tsc -b` during `npm run build`)
