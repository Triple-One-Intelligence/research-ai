# Project Setup

## Configuration

This project requires a local environment configuration file that is not tracked in git for security reasons.

To set this up:

1.  **Copy the example file:**
    ```bash
    cp kube/research-ai.env.example kube/research-ai.env
    ```
2.  **Add credentials:** Open the newly created `kube/research-ai.env` and fill in your specific values/credentials.

## Makefile Usage

Use `make` to manage the application lifecycle.

| Command | Description |
| --- | --- |
| **Development** |  |
| `make up` | Builds dev images and deploys the pod using values from `.env`. |
| `make down` | Stops and removes the local pod. |
| `make watch` | Tails logs for the entire pod. |
| `make wapi` / `wui` | Tails logs for the API or Frontend specifically. |
| `make labelSELinux` | Relabels files for OSes running a security-hardened Linux kernel. |
| **Production** |  |
| `make deploy` | Builds prod images and installs Systemd Quadlet units. |
| `make undeploy` | Stops services and removes Quadlet units/env files. |
| `make logs` | Tails combined systemd journals for all services. |
| `make logs-api` | Tails journals for the API service only. |
| `make logs-ui` | Tails journals for the frontend service only. |
| `make logs-ric` | Tails journals for the ricgraph service only. |
| **Maintenance** |  |
| `make nuke` | **The Nuclear Option:** Wipes all containers, pods, volumes, and images. |

## Gitignore Policy

**Do not clutter the project `.gitignore` with personal tooling configurations.**

This repository maintains a strict, minimal `.gitignore` focused only on project-specific artifacts and security. If your specific tools or OS generate files (e.g., `.vscode/`, `.idea/`, `.DS_Store`, `venv/`), you must add them to your **Global Gitignore**.

* *Learn how to set up a global gitignore [here](https://docs.github.com/en/get-started/getting-started-with-git/ignoring-files#configuring-ignored-files-for-all-repositories-on-your-computer).*