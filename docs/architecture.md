# Research AI - System Architecture

## System Overview

```
                         +------------------+
                         |     Caddy        |
                         | (reverse proxy)  |
                         +--------+---------+
                                  |
                    +-------------+-------------+
                    |                           |
           +-------v--------+         +--------v-------+
           |    Frontend     |         |      API       |
           | React/Vite/TS  |         |    FastAPI      |
           | :5173           |         |    :8000        |
           +----------------+         +---+----+----+---+
                                          |    |    |
                          +---------------+    |    +---------------+
                          |                    |                    |
                  +-------v------+    +--------v-------+   +-------v------+
                  |    Neo4j     |    |    Ollama       |   |  Ricgraph    |
                  | Graph DB     |    | LLM / Embed    |   | (external)   |
                  | :7687        |    | :11434          |   | :3030        |
                  +--------------+    +----------------+   +--------------+
```

## Services

### Frontend (React + Vite + TypeScript)

Three-panel layout:
- **LeftPanel** - search autocomplete, prompt input
- **MiddlePanel** - AI response (streamed via SSE)
- **RightPanel** - entity connections graph

Internationalization with i18n (English and Dutch). AI responses stream from the API using Server-Sent Events.

### API (FastAPI / Python)

Routers:
- `/autocomplete` - fulltext search on Neo4j node values
- `/connections` - graph traversal for entity relationships
- `/generate` - direct LLM generation, optionally RAG-scoped to an entity
- `/embed` - text embedding via Ollama
- `/health` - service health checks

Uses the Neo4j Python driver for all graph queries.

### Neo4j (Graph Database)

Stores the Ricgraph knowledge graph: persons, organizations, and DOI publications as `RicgraphNode` nodes connected by `LINKS_TO` relationships. Provides fulltext indexing for autocomplete and vector indexing for semantic search over publication embeddings.

### Ricgraph (External Research Graph Service)

External service that harvests research metadata from sources like OpenAlex and ORCID, then stores the result as a node graph in Neo4j.

### Ollama (AI / LLM Service)

Runs local LLM models:
- **tinyllama** - chat / generation
- **nomic-embed-text** - text embeddings for RAG

## Data Flow

### Harvest
Ricgraph harvests from OpenAlex / ORCID and writes `RicgraphNode` nodes and `LINKS_TO` relationships into Neo4j.

### Enrich
`scripts/enrich.py` fetches publication abstracts from OpenAlex, generates vector embeddings via Ollama (`nomic-embed-text`), and stores both the abstract and embedding on Neo4j DOI nodes.

### Search
1. User types in autocomplete input
2. API queries Neo4j fulltext index (`ValueFulltextIndex`) on node values
3. User selects an entity
4. API runs a connections query to return linked nodes

### RAG (Retrieval-Augmented Generation)
1. User submits a prompt
2. API embeds the prompt via Ollama
3. Vector similarity search (`publicationEmbeddingIndex`) finds relevant publications
4. A system prompt is built with retrieved context
5. LLM response streams back to the frontend via SSE

## Neo4j Graph Model

**Node label:** `RicgraphNode`

| Property    | Description                              |
|-------------|------------------------------------------|
| `name`      | Property key (e.g. FULL_NAME, DOI)       |
| `value`     | Property value                           |
| `category`  | Node category (person, organization ...) |
| `abstract`  | Publication abstract (DOI nodes)         |
| `embedding` | Vector embedding of abstract (DOI nodes) |

**Relationship:** `LINKS_TO` (connects all related nodes)

**Graph structure:** Person root nodes link to publication DOI nodes and organization nodes.

**Indexes:**
- `ValueFulltextIndex` - fulltext index on `value` property (autocomplete)
- `publicationEmbeddingIndex` - vector index on `embedding` property (RAG similarity search)

## Environment & Networking

### Development
- SSH tunnel to production Neo4j, Ollama, and Ricgraph
- Local API and frontend served through Caddy

### Production
- All containers run in a Podman pod
- Caddy reverse proxy with automatic HTTPS

### Configuration
- `.env` files for service URLs, credentials, model names
- `LOGLEVEL` environment variable controls Python logging verbosity
