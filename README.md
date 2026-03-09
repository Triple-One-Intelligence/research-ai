# Research AI

A research publication discovery platform that combines [Ricgraph](https://github.com/UtrechtUniversity/ricgraph) with AI-powered semantic search. It harvests research metadata into a Neo4j graph database, enriches publications with abstracts and vector embeddings, and exposes a search API with a web frontend.

## Architecture

```
┌──────────────┐    ┌──────────────┐    ┌──────────────┐
│   Frontend   │◄──►│     API      │◄──►│    Neo4j     │
│   (Vue/Vite) │    │   (FastAPI)  │    │  (Graph DB)  │
└──────────────┘    └──────┬───────┘    └──────▲───────┘
                           │                   │
                    ┌──────▼───────┐    ┌──────┴───────┐
                    │    Ollama    │    │   Ricgraph   │
                    │   (AI/LLM)   │    │  (Harvester) │
                    └──────────────┘    └──────────────┘
```

- **Frontend** — Vue.js SPA for searching and browsing researchers and publications
- **API** — FastAPI backend handling search queries, autocomplete, and the enrichment pipeline
- **Neo4j** — Graph database storing Ricgraph nodes (researchers, publications, DOIs, etc.) and vector embeddings
- **Ricgraph** — Harvests research metadata from external sources (e.g. Pure, OpenAlex) into Neo4j
- **Ollama** — Local AI service for generating text embeddings and powering semantic search

### Data Pipeline

1. **Harvest** — Ricgraph harvests researcher and publication metadata into Neo4j
2. **Enrich** — The enrichment script fetches abstracts from OpenAlex, generates vector embeddings via Ollama, and stores them on the Neo4j nodes
3. **Search** — The API supports both fulltext search (exact/fuzzy matching) and vector similarity search (semantic meaning)

## Quick Start

```bash
# 1. Copy and fill in your environment config
cp kube/research-ai-dev.env.example kube/research-ai-dev.env

# 2. Start the dev pod + SSH tunnel to the remote Neo4j/Ollama
make dev
```

See [docs/development.md](docs/development.md) for the full development guide, WSL setup, Makefile reference, and deployment workflow.

## License

This project is licensed under the [GNU General Public License v3.0](LICENSE).
