# Research AI

A research publication discovery platform that combines [Ricgraph](https://github.com/UtrechtUniversity/ricgraph) with AI-powered semantic search. It harvests research metadata into a Neo4j graph database, enriches publications with abstracts and vector embeddings, and exposes a search API with a web frontend.

## Architecture

```
┌──────────────┐    ┌──────────────┐    ┌──────────────┐
│   Frontend   │◄──►│     API      │◄──►│    Neo4j     │
│  (React/Vite)│    │   (FastAPI)  │    │  (Graph DB)  │
└──────────────┘    └──────┬───────┘    └──────▲───────┘
                           │                   │
                    ┌──────▼───────┐    ┌──────┴───────┐
                    │    Ollama    │    │   Ricgraph   │
                    │   (AI/LLM)   │    │  (Harvester) │
                    └──────────────┘    └──────────────┘
```

- **Frontend** — React SPA for searching and browsing researchers and publications
- **API** — FastAPI backend handling search queries, autocomplete, and AI chat (streamed via SSE)
- **Neo4j** — Graph database storing Ricgraph nodes (researchers, publications, DOIs, etc.) and vector embeddings
- **Ricgraph** — Harvests research metadata from external sources (e.g. Pure, OpenAlex) into Neo4j
- **Ollama** — Local AI service for generating text embeddings and powering semantic search and chat

### Data Pipeline

1. **Harvest** — Ricgraph harvests researcher and publication metadata into Neo4j
2. **Enrich** — The enrichment script fetches abstracts from OpenAlex, generates vector embeddings via Ollama, and stores them on the Neo4j nodes
3. **Search** — The API supports both fulltext search (exact/fuzzy matching) and vector similarity search (semantic meaning)

## Quick Start

### 1. Get the environment file

The dev environment connects to the production server via an SSH tunnel. You need an env file with the server address and credentials.

**Option A** — Generate it from the production server:

```bash
ssh root@<server-ip>
cd research-ai/
make dev-env-info
```

Copy the output between the `--- cut here ---` markers into `kube/research-ai-dev.env`.

**Option B** — Copy from the example and fill in manually:

```bash
cp kube/research-ai-dev.env.example kube/research-ai-dev.env
```

Edit `kube/research-ai-dev.env` and set at least:
- `REMOTE_SERVER` — SSH user@host for the production server
- `REMOTE_NEO4J_PASS` — Neo4j password (ask a team member)

### 2. Verify SSH access

```bash
ssh root@<server-ip> echo ok
```

### 3. Start the dev environment

```bash
make dev
```

This builds the containers, opens an SSH tunnel to the remote services, runs the test suite, and serves the app at **https://localhost:3000**.

See [docs/development.md](docs/development.md) for the full development guide, WSL setup, Makefile reference, and deployment workflow.

## License

This project is licensed under the [GNU General Public License v3.0](LICENSE).
