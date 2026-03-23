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

Volledige instructies: **`docs/server-a-setup.md`**

Preview pods gebruiken de bestaande Neo4j en Ollama op de server.
Geen aparte instanties nodig. Credentials blijven lokaal op de server.

- [ ] Runner user aanmaken + runner installeren (zie `docs/server-a-setup.md`)
- [ ] CI env file aanmaken: `/home/github-runner/.env.ci` (zie setup doc)
- [ ] Firewall: poorten 4000-4100 openen voor preview pods
- [ ] Verifiëren: runner groen in GitHub, `nc -z localhost 7687` OK
- [ ] Afspreken met team: niet meer SSH'en naar Server A om te ontwikkelen

---

## Server B — `kosher` (sandbox)

Volledige instructies: **`docs/server-b-setup.md`**

- [ ] Documenteren richting team dat Server B de sandbox is
- [ ] Optioneel: eigen Neo4j voor offline werk (zie setup doc)

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
