# Server A Setup — `researchaicloud` (productie + CI runner)

Dit document beschrijft hoe je de GitHub Actions self-hosted runner installeert
op Server A. Na deze stappen kan CI automatisch preview pods aanmaken voor PRs.

## Vereisten

- SSH toegang tot Server A als root
- Repo admin rechten op GitHub (voor runner token)
- Neo4j en Ollama draaien al op de server

## Stap 1: Runner user aanmaken

```bash
sudo useradd -m -s /bin/bash github-runner
sudo loginctl enable-linger github-runner
```

Geef de runner user toegang tot podman:

```bash
sudo usermod -aG systemd-journal github-runner
```

## Stap 2: Runner token ophalen

Op je **laptop** (niet op de server):

```bash
gh api repos/Triple-One-Intelligence/research-ai/actions/runners/registration-token \
  -X POST --jq '.token'
```

Kopieer het token. Het is 1 uur geldig.

## Stap 3: Runner installeren

Op Server A:

```bash
sudo su - github-runner
mkdir actions-runner && cd actions-runner

# Download runner (check https://github.com/actions/runner/releases voor de laatste versie)
curl -o actions-runner-linux-x64-2.323.0.tar.gz -L \
  https://github.com/actions/runner/releases/download/v2.323.0/actions-runner-linux-x64-2.323.0.tar.gz
tar xzf ./actions-runner-linux-x64-2.323.0.tar.gz

./config.sh \
  --url https://github.com/Triple-One-Intelligence/research-ai \
  --token <PLAK_TOKEN_HIER> \
  --labels linux,production \
  --name research-ai-runner \
  --unattended

exit  # terug naar root
```

## Stap 4: Runner als systemd service starten

```bash
cd /home/github-runner/actions-runner
sudo ./svc.sh install github-runner
sudo ./svc.sh start
sudo ./svc.sh status  # controleer of het draait
```

## Stap 5: CI env file aanmaken

De CI workflow leest alle credentials uit een lokaal bestand op de server.
Er worden geen wachtwoorden in GitHub opgeslagen.

Maak het bestand aan op basis van de bestaande server configuratie:

```bash
sudo -u github-runner bash -c 'cat > /home/github-runner/.env.ci << EOF
# CI preview pods — credentials voor services op deze server
# Pas de waarden aan naar wat er op DEZE server draait.

# Neo4j (zelfde als productie, op deze server)
REMOTE_NEO4J_URL=bolt://host.containers.internal:7687
REMOTE_NEO4J_USER=neo4j
REMOTE_NEO4J_PASS=<WACHTWOORD_VAN_NEO4J_OP_DEZE_SERVER>

# Ollama (zelfde als productie, op deze server)
AI_SERVICE_URL=http://host.containers.internal:11434

# AI modellen (moet matchen met wat Ollama heeft geladen)
CHAT_MODEL=command-r:35b
EMBED_MODEL=snowflake-arctic-embed2
EMBED_DIMENSIONS=1024

# Overige
RICGRAPH_URL=http://host.containers.internal:18080
LOGLEVEL=INFO
EOF
chmod 600 /home/github-runner/.env.ci'
```

**Let op:** `host.containers.internal` is hoe containers binnen een podman pod
de host machine bereiken. Gebruik dit in plaats van `localhost`.

**Tip:** het Neo4j wachtwoord vind je in het bestaande prod env bestand op de server,
of via `podman inspect` op de draaiende Neo4j container.

## Stap 6: Firewall openen voor preview pods

Preview pods draaien op poorten 4000-4100 (gebaseerd op PR nummer):

```bash
# Controleer eerst of er al een firewall actief is:
sudo firewall-cmd --state 2>/dev/null || echo "Geen firewall actief"

# Als firewalld actief is:
sudo firewall-cmd --permanent --add-port=4000-4100/tcp
sudo firewall-cmd --reload
```

## Stap 7: Verifiëren

1. Check of de runner groen is:
   ```bash
   # Op je laptop:
   gh api repos/Triple-One-Intelligence/research-ai/actions/runners --jq '.runners[] | "\(.name): \(.status)"'
   ```

2. Check of het env bestand er is:
   ```bash
   sudo -u github-runner test -f /home/github-runner/.env.ci && echo "OK" || echo "MISSING"
   ```

3. Check of Neo4j en Ollama bereikbaar zijn:
   ```bash
   nc -z localhost 7687 && echo "Neo4j: OK" || echo "Neo4j: DOWN"
   nc -z localhost 11434 && echo "Ollama: OK" || echo "Ollama: DOWN"
   ```

## Wat als je een andere server wilt gebruiken?

De CI workflow is niet gekoppeld aan een specifieke server. Het enige wat telt
zijn de runner **labels** (`linux`, `production`). Om te wisselen:

1. Installeer een runner op de nieuwe server (dezelfde stappen)
2. Maak een `.env.ci` aan met de credentials van die server
3. De-registreer de oude runner: `./config.sh remove --token <TOKEN>`

De workflow pakt automatisch de nieuwe runner op.
