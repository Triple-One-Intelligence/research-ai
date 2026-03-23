# Server B Setup — `kosher` (sandbox)

Server B is een vrije speeltuin voor ontwikkelaars. Hier kan je experimenteren
zonder de productieomgeving of CI te beïnvloeden.

## Hoe te gebruiken

### Optie 1: Zelfde workflow als laptop (SSH tunnel naar Server A)

Clone de repo, kopieer het dev env bestand, en draai `make dev`:

```bash
git clone git@github.com:Triple-One-Intelligence/research-ai.git
cd research-ai

# Kopieer het dev env bestand (pas REMOTE_SERVER aan naar Server A's IP)
cp kube/research-ai-dev.env.example kube/research-ai-dev.env
# Edit kube/research-ai-dev.env met de juiste waarden

make dev
```

Dit start een SSH tunnel naar Server A voor Neo4j + Ollama, en draait de
app lokaal op Server B.

### Optie 2: Eigen Neo4j voor offline werk

Als je zonder Server A wilt werken:

```bash
podman run -d --name neo4j-sandbox \
  -p 7687:7687 -p 7474:7474 \
  -e NEO4J_AUTH=neo4j/sandbox \
  -v neo4j-sandbox-data:/data \
  docker.io/library/neo4j:5
```

Pas dan `kube/research-ai-dev.env` aan:
```
REMOTE_NEO4J_URL=bolt://localhost:7687
REMOTE_NEO4J_PASS=sandbox
```

**Let op:** de 3080 Ti op Server B heeft niet genoeg VRAM voor Command-R 35B.
AI-gerelateerde tests en endpoints zullen skippen of falen.

## Regels

- Server B is NIET voor CI — daar is Server A voor
- Meerdere mensen kunnen tegelijk op Server B werken (gebruik eigen branches)
- Breek je iets? Geen probleem — het is een sandbox
- Productie draait op Server A en wordt niet beïnvloed
