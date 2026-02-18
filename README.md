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