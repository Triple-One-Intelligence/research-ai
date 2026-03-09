# Development Guide

## Prerequisites

- [Podman](https://podman.io/) (used instead of Docker)
- SSH access to the remote server (for `make tunnel` / `make dev`)
- Git

## Configuration

This project requires a local environment configuration file that is not tracked in git for security reasons.

```bash
# For development
cp kube/research-ai-dev.env.example kube/research-ai-dev.env

# For production
cp kube/research-ai-prod.env.example kube/research-ai-prod.env
```

Open the newly created `.env` file and fill in the required credentials.

## Getting Started

```bash
# Start the dev pod and SSH tunnel to the remote server
make dev

# Or start them separately:
make up       # Build and start the local dev pod
make tunnel   # Open SSH tunnel to the remote Neo4j/Ollama

# Run the enrichment pipeline (fetches abstracts + generates embeddings)
make enrich
```

## WSL (Windows) Setup

If you are developing on Windows using WSL, there is one extra consideration: your SSH keys live on the Windows side and need to be accessible from WSL for the tunnel to work.

This is handled automatically. When you run `make dev` or `make tunnel`, it first runs `make setup-wsl-ssh` which:

1. Detects whether you are running inside WSL
2. If so, symlinks your Windows SSH keys (`C:\Users\<you>\.ssh`) into `~/.ssh` inside WSL
3. If you are on native Linux, it does nothing

If the symlink already exists it is skipped. You can also run it manually:

```bash
make setup-wsl-ssh
```

### Other WSL tips

- Make sure your Windows SSH key has been added to the remote server's `authorized_keys`
- If you get permission errors on the SSH key, WSL may be mounting it with too-open permissions. You can fix this by adding to `/etc/wsl.conf`:
  ```ini
  [automount]
  options = "metadata,umask=22,fmask=177"
  ```
  Then restart WSL with `wsl --shutdown` and try again.

## SELinux (Fedora / RHEL)

If you are developing on an OS with a security-hardened Linux kernel (e.g. Fedora with SELinux enforcing), container volume mounts may be denied. Run:

```bash
make labelSELinux
```

This relabels the project files so Podman containers can access them.

## Makefile Reference

| Command | Description |
| --- | --- |
| **Development** |  |
| `make dev` | Builds dev images, starts the pod, and opens an SSH tunnel to the remote server. |
| `make up` | Builds dev images and deploys the local development pod. |
| `make down` | Stops and removes the local pod. |
| `make tunnel` | Opens an SSH tunnel forwarding Neo4j (7687, 7474), API (8080), frontend (3030), and Ollama (11434) from the remote server. |
| `make watch` | Tails logs for the entire pod. |
| `make wapi` / `make wui` | Tails logs for the API or frontend container. |
| `make labelSELinux` | Relabels files for SELinux (Fedora/RHEL). |
| `make setup-wsl-ssh` | (WSL only) Symlinks Windows SSH keys into WSL. No-op on native Linux. |
| **Data Pipeline** |  |
| `make enrich` | Runs the enrichment pipeline: fetches abstracts from OpenAlex and generates vector embeddings. |
| `make enrich-force` | Same as `enrich`, but re-processes all publications (including already enriched ones). |
| `make harvest` | Triggers a Ricgraph harvest inside the Ricgraph container. |
| **Production** |  |
| `make deploy` | Builds prod images, creates the Podman network, and installs Systemd Quadlet units. |
| `make undeploy` | Stops services and removes Quadlet units. |
| `make logs` | Tails combined systemd journals for all services. |
| `make logs-api` / `make logs-ui` / `make logs-ric` | Tails journals for a specific service. |
| **Maintenance** |  |
| `make nuke` | Wipes all containers, pods, volumes, and images from the system. |

## Deployment Workflow

Follow these steps to deploy changes or test branches on the remote server.

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
