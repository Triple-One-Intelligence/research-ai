# Research AI

A research publication discovery platform that combines [Ricgraph](https://github.com/UtrechtUniversity/ricgraph) with AI-powered semantic search. It harvests research metadata into a Neo4j graph database, enriches publications with abstracts and vector embeddings, and exposes a search API with a web frontend.

## Architecture

```
┌──────────────┐    ┌──────────────┐    ┌──────────────┐
│   Frontend   │◄──►│   API        │◄──►│   Neo4j      │
│   (Vue/Vite) │    │   (FastAPI)  │    │   (Graph DB)  │
└──────────────┘    └──────┬───────┘    └──────▲───────┘
                           │                    │
                    ┌──────▼───────┐    ┌───────┴──────┐
                    │   Ollama     │    │   Ricgraph   │
                    │   (AI/LLM)   │    │  (Harvester) │
                    └──────────────┘    └──────────────┘
```

- **Frontend** — Vue.js SPA for searching and browsing researchers and publications
- **API** — FastAPI backend handling search queries, autocomplete, and the enrichment pipeline
- **Neo4j** — Graph database storing all Ricgraph nodes (researchers, publications, DOIs, etc.) and vector embeddings
- **Ricgraph** — Harvests research metadata from external sources (e.g. Pure, OpenAlex) into Neo4j
- **Ollama** — Local AI service for generating text embeddings and powering semantic search

### Data Pipeline

1. **Harvest** — Ricgraph harvests researcher and publication metadata into Neo4j
2. **Enrich** — The enrichment script (`make enrich`) fetches abstracts from OpenAlex for each DOI, generates vector embeddings via Ollama, and stores them on the Neo4j nodes
3. **Search** — The API supports both fulltext search (exact/fuzzy matching) and vector similarity search (semantic meaning)

## Configuration

This project requires a local environment configuration file that is not tracked in git for security reasons.

To set this up:

1.  **Copy the example file:**
    ```bash
    cp kube/research-ai-dev.env.example kube/research-ai-dev.env
    ```
    or
    ```bash
    cp kube/research-ai-prod.env.example kube/research-ai-prod.env
    ```
    for production
2.  **Add credentials:** Open the newly created `.env` file and fill in your specific values/credentials.

## Development

### Prerequisites

- [Podman](https://podman.io/) (used instead of Docker)
- SSH access to the remote server (for `make tunnel` / `make dev`)

### Getting Started

```bash
# 1. Copy and fill in your environment config
cp kube/research-ai-dev.env.example kube/research-ai-dev.env

# 2. Start the dev pod + SSH tunnel to the remote Neo4j/Ollama
make dev

# 3. (Optional) Run the enrichment pipeline to generate embeddings
make enrich
```

On **WSL**, `make dev` automatically symlinks your Windows SSH keys so the tunnel works. On native Linux this step is skipped.

## Makefile Usage

Use `make` to manage the application lifecycle.

| Command | Description |
| --- | --- |
| **Development** |  |
| `make tunnel` | Establishes an SSH tunnel to the remote server, forwarding the remote Neo4j, Ricgraph, and AI ports securely to your localhost. |
| `make up` | Builds dev images and deploys the local development pod using values from kube/research-ai-dev.env. |
| `make down` | Stops and removes the local pod. |
| `make watch` | Tails logs for the entire pod. |
| `make wapi` / `wui` | Tails logs for the API or Frontend specifically. |
| `make labelSELinux` | Relabels files for OSes running a security-hardened Linux kernel. |
| **Production** |  |
| `make deploy` | Builds prod images, creates the isolated Podman network, and installs the Systemd Quadlet units using kube/research-ai-prod.env. |
| `make undeploy` | Stops services and removes Quadlet units/env files. |
| `make logs` | Tails combined systemd journals for all services. |
| `make logs-api` | Tails journals for the API service only. |
| `make logs-ui` | Tails journals for the frontend service only. |
| `make logs-ric` | Tails journals for the ricgraph service only. |
| `make enrich` | Runs the enrichment pipeline: fetches abstracts from OpenAlex and generates vector embeddings for publication nodes in Neo4j. |
| `make enrich-force` | Same as `enrich`, but re-enriches all publications including those that already have abstracts. |
| `make harvest` | Triggers a Ricgraph harvest inside the Ricgraph container. |
| **Maintenance** |  |
| `make nuke` | **The Nuclear Option:** Wipes all containers, pods, volumes, and images. |
| `make setup-wsl-ssh` | (WSL only) Symlinks Windows SSH keys into WSL so the SSH tunnel works. No-op on native Linux. |


## Deployment Workflow

Follow these steps to deploy changes or test branches on the remote server.

**1. Connect to the Server**
Connect via SSH (e.g., from WSL or your terminal):

```bash
ssh root@0xai.nl
```

**2. Navigate to the Project**
Move to the repository directory:

```bash
cd research-ai/
```

**3. Deploy a Feature Branch**
To test or deploy a specific branch:

1. **Stop the current version:**
```bash
make undeploy
```


2. **Switch to your branch and update:**
```bash
git checkout <your-branch-name>
git pull
```


3. **Deploy:**
```bash
make deploy
```


**4. Restore Master (Stable)**
To revert the server to the main stable version:

1. **Stop the current version:**
```bash
make undeploy
```


2. **Switch back to master and update:**
```bash
git checkout master
git pull
```


3. **Redeploy stable:**
```bash
make deploy
```


## Gitignore Policy

**Do not clutter the project `.gitignore` with personal tooling configurations.**

This repository maintains a strict, minimal `.gitignore` focused only on project-specific artifacts and security. If your specific tools or OS generate files (e.g., `.vscode/`, `.idea/`, `.DS_Store`, `venv/`), you must add them to your **Global Gitignore**.

* *Learn how to set up a global gitignore [here](https://docs.github.com/en/get-started/getting-started-with-git/ignoring-files#configuring-ignored-files-for-all-repositories-on-your-computer).*