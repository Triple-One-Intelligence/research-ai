# CI/CD Setup — TODO per rol

## Repo Admin (GitHub Settings)

### Al gedaan (via `gh` CLI)

- [x] **Branch protection op master** — require PR (1 approval), dismiss stale reviews, CODEOWNERS review required
- [x] **Required status checks**: `test-api`, `build-frontend`, `branch-name`
- [x] **Admin bypass**: aan (tijdelijk, voor eerste merge van CI branch)
- [x] **Squash merge only** — merge commits en rebase uit
- [x] **Auto-delete head branches** na merge
- [x] **Production environment** — reviewers: @Lukasvd123 + @jandre-d, alleen master
- [x] **`CLAUDE_CODE_OAUTH_TOKEN`** secret aanwezig
- [x] Neo4j credentials via server-local env file (niet in GitHub secrets)

### Nog te doen

- [ ] **Na merge van CI branch: admin bypass uitzetten**
  ```bash
  gh api repos/Triple-One-Intelligence/research-ai/branches/master/protection/enforce_admins \
    -X POST
  ```
- [ ] **Na merge: require up-to-date branches aanzetten**
  ```bash
  gh api repos/Triple-One-Intelligence/research-ai/branches/master/protection/required_status_checks \
    -X PATCH --input - <<< '{"strict": true, "contexts": ["test-api", "build-frontend", "branch-name"]}'
  ```
- [ ] **CodeQL aanzetten** — Settings → Code security → Enable CodeQL
- [ ] **Ontbrekende org leden uitnodigen** (eerdere contributors):
  - [ ] ThijmenLigter (115 Python commits — meest actieve backend dev)
  - [ ] Anou212 (frontend)
  - [ ] Strike6782 (frontend)
  - [ ] 0989711 / Onno Meppelink (frontend)
  - [ ] sybren / zop12345 (46 API commits — GitHub username bevestigen)

---

## Server A — `researchaicloud` (productie + CI)

Server A draait productie EN CI preview pods. Nadat de repo admin alles heeft
ingesteld, doe het volgende op Server A:

### Self-hosted runner installeren

- [ ] Runner user aanmaken:
  ```bash
  sudo useradd -m -s /bin/bash github-runner
  sudo loginctl enable-linger github-runner
  ```
- [ ] GitHub Actions runner installeren:
  ```bash
  sudo su - github-runner
  mkdir actions-runner && cd actions-runner
  # Download URL en token komen van GitHub UI:
  # Settings → Actions → Runners → New self-hosted runner → Linux x64
  curl -o actions-runner-linux-x64-2.XXX.X.tar.gz -L <URL>
  tar xzf ./actions-runner-linux-x64-2.XXX.X.tar.gz
  ./config.sh --url https://github.com/Triple-One-Intelligence/research-ai \
              --token <TOKEN> \
              --labels linux,production \
              --name research-ai-runner \
              --unattended
  ```
- [ ] Runner als systemd service:
  ```bash
  exit  # terug naar sudo user
  cd /home/github-runner/actions-runner
  sudo ./svc.sh install github-runner
  sudo ./svc.sh start
  ```
- [ ] Verifiëren dat runner groen is in GitHub Settings → Actions → Runners
- [ ] Dev Neo4j env file aanmaken (CI leest credentials hier, niet van GitHub secrets):
  ```bash
  cat > /home/github-runner/.env.dev-neo4j << 'ENVEOF'
  REMOTE_NEO4J_URL=bolt://localhost:7688
  REMOTE_NEO4J_USER=neo4j
  REMOTE_NEO4J_PASS=<DEV_NEO4J_WACHTWOORD>
  ENVEOF
  chmod 600 /home/github-runner/.env.dev-neo4j
  chown github-runner:github-runner /home/github-runner/.env.dev-neo4j
  ```

### Dev Neo4j instantie (naast productie)

Preview pods gebruiken een aparte Neo4j zodat productiedata niet geraakt wordt.

- [ ] Dev Neo4j container starten op port 7688:
  ```bash
  podman run -d --name neo4j-dev \
    -p 7688:7687 -p 7475:7474 \
    -e NEO4J_AUTH=neo4j/<DEV_WACHTWOORD> \
    -v neo4j-dev-data:/data \
    docker.io/library/neo4j:5
  ```
- [ ] Dev data laden vanuit backup:
  ```bash
  # Eerst backup maken van productie (als dat nog niet is gedaan):
  make neo4j-backup
  # Dan restoren naar dev instantie — zie Makefile voor het juiste commando
  ```
- [ ] Verifiëren: `nc -z localhost 7688` moet slagen
- [ ] Dev Neo4j credentials toevoegen als GitHub secrets (zie Repo Admin sectie)

### SSH toegang beperken (afspraak)

- [ ] Afspreken met team: **niet meer SSH'en naar Server A om te ontwikkelen**
  - Gebruik de preview link in de PR om je branch te bekijken
  - Server B (kosher) is beschikbaar als sandbox
  - Alleen Lukas en Jelmer houden SSH toegang voor noodgevallen

### Firewall: preview poorten openen

- [ ] Poortrange 4000-4100 openen voor inkomend verkeer (preview pods)
  ```bash
  sudo firewall-cmd --permanent --add-port=4000-4100/tcp
  sudo firewall-cmd --reload
  ```

---

## Server B — `kosher` (sandbox)

Server B is een vrije speeltuin voor ontwikkelaars. Geen CI, geen structuur.

- [ ] Documenteren richting team dat Server B de sandbox is
- [ ] Optioneel: eigen Neo4j installeren voor offline ontwikkeling
  ```bash
  podman run -d --name neo4j-sandbox \
    -p 7687:7687 -p 7474:7474 \
    -e NEO4J_AUTH=neo4j/sandbox \
    -v neo4j-sandbox-data:/data \
    docker.io/library/neo4j:5
  ```
- [ ] Optioneel: data laden vanuit Server A backup

---

## Na alles: verifiëren

- [ ] Maak een test-PR aan en controleer:
  - [ ] Unit tests + frontend build draaien op GitHub-hosted runners
  - [ ] Preview pod wordt aangemaakt op Server A
  - [ ] Preview URL wordt als comment in de PR gepost
  - [ ] Integration tests draaien tegen de preview pod
  - [ ] Preview pod wordt opgeruimd bij PR sluiten/mergen
- [ ] Controleer security:
  - [ ] PR van een extern fork → geen Claude review
  - [ ] PR van een teamlid → wel Claude review
  - [ ] `@claude` mention van een niet-collaborator → genegeerd
- [ ] Controleer manual test warning:
  - [ ] PR die `api/app/utils/ai_utils/` wijzigt → warning comment
- [ ] Controleer CODEOWNERS:
  - [ ] PR in `/api/` → @ThijmenLigter + @Lukasvd123 als reviewers
  - [ ] PR in `/frontend/` → @Lukasvd123 + @Strike6782 + @Anou212 + @TimonZ4
- [ ] Controleer Dependabot:
  - [ ] Python deps → @ThijmenLigter + @Lukasvd123
  - [ ] npm deps → @Lukasvd123 + @Strike6782
  - [ ] GitHub Actions → @Lukasvd123 + @jandre-d

---

## GitHub username mapping — nog te achterhalen

- [ ] **sybren** (s.c.m.vandermeijden@students.uu.nl) — 46 API commits, derde meest actieve contributor
  - GitHub username onbekend → toevoegen aan CODEOWNERS `/api/` zodra bekend
- [ ] Bevestig of `zop12345` (sybcomi2006@gmail.com) dezelfde persoon is als sybren

---

## Al gedaan (in deze branch)

- [x] CI workflow: unit tests + frontend build + branch name validatie
- [x] CI workflow: preview pods per PR met integration tests
- [x] CI workflow: integration tests op push to master
- [x] CI workflow: auto-deploy met environment approval gate
- [x] CI workflow: path-based routing (frontend-only skip, manual test warning)
- [x] CI workflow: concurrency groups (cancel stale PR runs)
- [x] Preview cleanup workflow: pod opruimen bij PR sluiten
- [x] PR checklist auto-tick: branch naming en CI resultaat automatisch afvinken
- [x] Claude Code Review: beperkt tot OWNER/MEMBER/COLLABORATOR (veilig voor publieke repo)
- [x] Dependabot configuratie met area-specifieke reviewers
- [x] CODEOWNERS gebaseerd op git commit analyse
- [x] PR template met CI checklist
- [x] PR auto-populate: YouTrack link automatisch invullen
- [x] Branch naming conventie check
- [x] Archive branch workflow: tag + delete na merge
- [x] `make dev` draait geen tests meer automatisch
- [x] Test URLs configureerbaar via environment variabelen
- [x] Developer workflow guide (`docs/dev-workflow.md`)
