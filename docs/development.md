# Development Guide

## Prerequisites

- [Podman](https://podman.io/) (used instead of Docker)
- SSH access to the remote server (for the tunnel to Neo4j, Ollama, etc.)
- Git
- Node.js (bundled in the dev container, not needed on host)
- Python 3 (for the test venv, auto-created by `make test`)

## Environment File

The dev environment tunnels to the production server for Neo4j, Ricgraph, and Ollama. Connection details are stored in `kube/research-ai-dev.env` (git-ignored).

### Option A: Generate from the production server

SSH into the production server and run:

```bash
ssh root@<server-ip>
cd research-ai/
make dev-env-info
```

This prints a ready-to-use env file. Copy everything between the `--- cut here ---` markers and save it as `kube/research-ai-dev.env` on your local machine.

### Option B: Copy from the example

```bash
cp kube/research-ai-dev.env.example kube/research-ai-dev.env
```

Open `kube/research-ai-dev.env` and fill in the values. The required fields are:

| Variable | Description |
| --- | --- |
| `REMOTE_SERVER` | SSH target for the tunnel, e.g. `root@145.38.194.46` |
| `REMOTE_NEO4J_PASS` | Neo4j password on the production server |

The rest can stay at their defaults for local development.

### Verify SSH access

Before starting, make sure you can reach the server:

```bash
ssh root@<server-ip> echo ok
```

If this hangs or fails, fix your SSH config/keys first.

## Getting Started

```bash
# Start everything: tunnel + pod + tests
make dev
```

This will:
1. Open an SSH tunnel to the remote server (Neo4j, Ricgraph, Ollama)
2. Build the API container image
3. Start the dev pod (API, frontend, Caddy reverse proxy)
4. Wait for the frontend (Vite) to be ready
5. Run the full test suite (unit + integration)
6. Print the URL: **https://localhost:3000**

The dev server uses a self-signed TLS certificate. Your browser will show a security warning on first visit — accept it to proceed.

### Starting components separately

```bash
make up         # Build and start the local dev pod (no tunnel)
make tunnel     # Open SSH tunnel only
make down       # Stop and remove the dev pod
```

### Running tests

```bash
make test        # Unit + integration tests
make test-unit   # Unit tests only (no pod needed)
make test-dev    # Integration tests only (needs running pod)
```

### Logs

```bash
make watch    # Tail all container logs
make wapi     # Tail API logs only
make wui      # Tail frontend logs only
```

### Data pipeline

```bash
make enrich        # Fetch abstracts + generate embeddings
make enrich-force  # Re-enrich all publications (including already done)
make harvest       # Run Ricgraph harvesting
```

## WSL (Windows) Setup

If you are developing on Windows using WSL:

1. Your SSH keys live on the Windows side and need to be accessible from WSL. This is handled automatically — `make dev` runs `make setup-wsl-ssh` which symlinks `C:\Users\<you>\.ssh` into `~/.ssh` inside WSL. On native Linux it does nothing.

2. If you get permission errors on the SSH key, WSL may mount it with too-open permissions. Add to `/etc/wsl.conf`:
   ```ini
   [automount]
   options = "metadata,umask=22,fmask=177"
   ```
   Then restart WSL with `wsl --shutdown` and try again.

3. If you see `: not found` errors when running `make dev`, the files have Windows line endings (CRLF). Pull the latest changes — the `.gitattributes` file enforces LF endings for all script and config files.

## SELinux (Fedora / RHEL)

If containers fail to access volume mounts, run:

```bash
make labelSELinux
```

This relabels the project files so Podman containers can read them.

## Makefile Reference

| Command | Description |
| --- | --- |
| **Development** | |
| `make dev` | Full dev environment: tunnel + pod + tests |
| `make up` / `make down` | Start / stop dev pod |
| `make tunnel` | SSH tunnel to remote services |
| `make tunnel-stop` | Stop the SSH tunnel |
| `make tunnel-status` | Check if the tunnel is running |
| `make watch` | Tail all container logs |
| `make wapi` / `make wui` | Tail API / frontend logs |
| `make setup-wsl-ssh` | (WSL only) Symlink Windows SSH keys |
| `make labelSELinux` | Relabel files for SELinux |
| **Testing** | |
| `make test` | Unit + integration tests |
| `make test-unit` | Unit tests only (offline) |
| `make test-dev` | Integration tests (needs running pod) |
| `make test-deploy` | Production smoke tests (run on server) |
| **Data** | |
| `make enrich` | Enrich publications (abstracts + embeddings) |
| `make enrich-force` | Re-enrich all publications |
| `make harvest` | Run Ricgraph harvesting |
| **Production** | |
| `make deploy` | Build + deploy to production |
| `make undeploy` | Stop + remove all production services |
| `make dev-env-info` | Print dev env config (run on server) |
| `make logs` | Tail all production logs |
| **Danger** | |
| `make nuke` | Destroy ALL containers, pods, volumes, images |

## Deployment Workflow

### 1. Connect to the server

```bash
ssh root@0xai.nl
cd research-ai/
```

### 2. Deploy a feature branch

```bash
make undeploy
git checkout <your-branch-name>
git pull
make deploy
```

### 3. Restore master (stable)

```bash
make undeploy
git checkout master
git pull
make deploy
```

## Gitignore Policy

**Do not clutter the project `.gitignore` with personal tooling configurations.**

This repository maintains a minimal `.gitignore` focused on project-specific artifacts and security. If your tools or OS generate files (e.g. `.vscode/`, `.idea/`, `.DS_Store`, `venv/`), add them to your [global gitignore](https://docs.github.com/en/get-started/getting-started-with-git/ignoring-files#configuring-ignored-files-for-all-repositories-on-your-computer) instead.
