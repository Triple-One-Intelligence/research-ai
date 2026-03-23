# Research-AI API Reference

## GET /health

Returns service status.

**Response:**

```json
{
  "status": "ok",
  "service": "Research-AI API",
  "time": "2025-01-15T10:30:00"
}
```

---

## GET /autocomplete

Autocomplete suggestions from fulltext search.

**Query Parameters:**

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `query` | str | yes | — | Partial search text (min 2 chars) |
| `limit` | int | no | 10 | Number of results (range 1-100) |

**Response:**

```json
{
  "persons": [{"author_id": "string", "name": "string"}],
  "organizations": [{"organization_id": "string", "name": "string"}]
}
```

**Errors:**

| Status | Description |
|--------|-------------|
| 400 | Query too short |
| 503 | Neo4j unavailable |
| 500 | Query failed |

---

## GET /connections/entity

Returns connections for an entity.

**Query Parameters:**

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `entity_id` | str | yes | — | Entity identifier |
| `entity_type` | str | yes | — | `"person"` or `"organization"` |
| `max_publications` | int | no | 50 | Max publications returned (range 1-200) |
| `max_collaborators` | int | no | 50 | Max collaborators returned (range 1-200) |
| `max_organizations` | int | no | 50 | Max organizations returned (range 1-200) |
| `max_members` | int | no | 50 | Max members returned (range 1-200) |

**Response:**

```json
{
  "entity_id": "string",
  "entity_type": "person",
  "collaborators": [{"author_id": "string", "name": "string"}],
  "publications": [{"doi": "string", "title": "string", "year": 2024, "category": "string", "versions": []}],
  "organizations": [{"organization_id": "string", "name": "string"}],
  "members": [{"author_id": "string", "name": "string"}]
}
```

**Errors:**

| Status | Description |
|--------|-------------|
| 400 | Invalid entity_type |
| 500 | Query failed |

---

## GET /connections/collaborators

Returns collaborator connections for an entity.

**Query Parameters:**

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `entity_id` | str | yes | — | Entity identifier |
| `entity_type` | str | yes | — | `"person"` or `"organization"` |
| `limit` | int | no | 50 | Max collaborators returned (range 1-200) |
| `cursor` | str | no | — | Pagination cursor (ignored for now) |

**Response:**

```json
{
  "entity_id": "string",
  "entity_type": "person",
  "collaborators": [{"author_id": "string", "name": "string"}],
  "cursor": "string | null"
}
```

**Errors:**

| Status | Description |
|--------|-------------|
| 400 | Invalid entity_type |
| 500 | Query failed |

---
## GET /connections/publications

Returns publication connections for an entity.

**Query Parameters:**

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `entity_id` | str | yes | — | Entity identifier |
| `entity_type` | str | yes | — | `"person"` or `"organization"` |
| `limit` | int | no | 50 | Max publications returned (range 1-200) |
| `cursor` | str | no | — | Pagination cursor (ignored for now) |

**Response:**

```json
{
  "entity_id": "string",
  "entity_type": "organization",
  "publications": [{"doi": "string", "title": "string", "year": 2024, "category": "string", "versions": []}],
  "cursor": "string | null"
}
```

**Errors:**

| Status | Description |
|--------|-------------|
| 400 | Invalid entity_type |
| 500 | Query failed |

---
## GET /connections/organizations

Returns organization connections for an entity.

**Query Parameters:**

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `entity_id` | str | yes | — | Entity identifier |
| `entity_type` | str | yes | — | `"person"` or `"organization"` |
| `limit` | int | no | 50 | Max organizations returned (range 1-200) |
| `cursor` | str | no | — | Pagination cursor (ignored for now) |

**Response:**

```json
{
  "entity_id": "string",
  "entity_type": "person",
  "organizations": [{"organization_id": "string", "name": "string"}],
  "cursor": "string | null"
}
```

**Errors:**

| Status | Description |
|--------|-------------|
| 400 | Invalid entity_type |
| 500 | Query failed |

---
## GET /connections/members

Returns member connections for an entity.

**Query Parameters:**

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `entity_id` | str | yes | — | Entity identifier |
| `entity_type` | str | yes | — | `"person"` or `"organization"` |
| `limit` | int | no | 50 | Max members returned (range 1-200) |
| `cursor` | str | no | — | Pagination cursor (ignored for now) |

**Response:**

```json
{
  "entity_id": "string",
  "entity_type": "organization",
  "members": [{"author_id": "string", "name": "string"}],
  "cursor": "string | null"
}
```

**Errors:**

| Status | Description |
|--------|-------------|
| 400 | Invalid entity_type |
| 500 | Query failed |

---
## POST /chat

Streaming chat (no RAG). Returns Server-Sent Events.

**Request Body:**

```json
{
  "model": "tinyllama",
  "messages": [{"role": "user", "content": "Hello"}],
  "stream": true,
  "options": {}
}
```

**SSE Events:**

```
data: {"token": "..."}\n\n
...
data: [DONE]\n\n
```

On error:

```
data: {"error": "..."}\n\n
```

---

## POST /generate

RAG-augmented generation. Embeds the prompt, retrieves similar publications from the vector index (scoped to entity), and streams the LLM response.

**Request Body:**

```json
{
  "prompt": "What are the main research areas?",
  "entity": {"id": "string", "type": "person", "label": "John Doe"},
  "top_k": 8
}
```

**SSE Events:**

When `LOGLEVEL=DEBUG`, the stream starts with a debug event:

```
data: {"debug": {...}}\n\n
```

Debug event fields: `model`, `user_prompt`, `entity`, `publications_found`, `publications`, `system_prompt`, `full_messages`.

Followed by token events:

```
data: {"token": "..."}\n\n
...
data: [DONE]\n\n
```

---

## POST /embed

Generate an embedding vector. Proxied from the Ollama embeddings API.

**Request Body:**

```json
{
  "model": "nomic-embed-text",
  "prompt": "text to embed"
}
```

**Response:** Proxied directly from Ollama embeddings API.
