# Development Workflow

## Overzicht

```
Laptop                    GitHub                    Server A (productie + CI)
  │                         │                              │
  ├─ Code schrijven         │                              │
  ├─ make test-unit         │                              │
  ├─ git push ──────────────┤                              │
  │                         ├─ Unit tests (GitHub-hosted)  │
  │                         ├─ Frontend build (GitHub-hosted)│
  │                         ├─ Preview pod starten ────────┤ podman pod op :40XX
  │                         ├─ Integration tests ──────────┤ pytest in pod
  │                         ├─ Preview URL in PR ──────────┤
  │                         ├─ Claude Code Review          │
  │                         │                              │
  ├─ Preview bekijken ──────┼──────────────────────────────┤ https://server:40XX
  │                         │                              │
  ├─ Code review            │                              │
  ├─ Merge to master ───────┤                              │
  │                         ├─ Deploy ─────────────────────┤ make deploy
  │                         │                              │
```

## Stap voor stap

### 1. Code schrijven (op je laptop)

Werk op je eigen machine. Je hebt geen SSH toegang tot Server A nodig.

```bash
git checkout -b feat/V26J-XXX-beschrijving
# ... code schrijven ...
```

### 2. Lokaal testen (optioneel, maar aangeraden)

Unit tests draaien volledig lokaal — geen Neo4j, geen GPU, geen server nodig.

```bash
cd api
pip install -r requirements.txt -r requirements-dev.txt
python -m pytest -m unit -v
```

Of via Make:

```bash
make test-unit
```

### 3. Push en open een PR

```bash
git push -u origin feat/V26J-XXX-beschrijving
```

Open een Pull Request naar `master` op GitHub.

### 4. CI doet de rest automatisch

Na het openen van een PR gebeurt dit automatisch:

| Stap | Waar | Wat |
|------|------|-----|
| Branch naming check | GitHub | Controleert of branch naam klopt |
| Unit tests | GitHub | `pytest -m unit` (volledig gemockt) |
| Frontend build | GitHub | `npm ci && npm run build` |
| Preview pod | Server A | Bouwt en start je branch in een geïsoleerde pod |
| Integration tests | Server A | `pytest` tegen je preview pod |
| Preview URL | PR comment | Link naar je draaiende branch |
| Code review | GitHub | Claude reviewt automatisch je code |
| YouTrack link | PR beschrijving | Automatisch ingevuld vanuit branch naam |

### 5. Preview bekijken

Na de CI verschijnt er een comment in je PR met een link:

> 🚀 **Preview environment** for this PR is running:
> **URL:** `https://researchaicloud:40XX`

Klik op de link om je branch live te bekijken in de browser. De preview
blijft draaien totdat de PR wordt gemerged of gesloten.

### 6. Code review en merge

- Claude Code Review post automatisch inline suggesties
- Een teamlid moet ook reviewen (CODEOWNERS)
- Na goedkeuring: **squash merge** naar master
- Na merge: automatische deploy naar productie

## Regels

| Regel | Reden |
|-------|-------|
| **Niet SSH'en naar Server A** | Preview links vervangen handmatige deploys. Server A is productie. |
| **Server B (kosher) is de sandbox** | Wil je experimenteren? Gebruik Server B. |
| **Branch naming: `type/ticket-beschrijving`** | CI controleert dit. Types: `feat/`, `fix/`, `test/`, `docs/`, `refactor/` |
| **Unit tests lokaal draaien voor je pusht** | `make test-unit` kost 5 seconden en vangt de meeste fouten |

## Wat als mijn PR AI/database code wijzigt?

Als je code wijzigt in `api/app/utils/ai_utils/`, `api/app/utils/database_utils/`,
`api/app/scripts/enrich.py`, `kube/`, of `Makefile`, verschijnt er een extra
waarschuwing in je PR:

> ⚠️ **Manual testing recommended**

Dit betekent dat je de wijziging handmatig moet testen op de productieomgeving
voordat je merget. Overleg met Lukas als je hulp nodig hebt.

## Veelgestelde vragen

**Kan ik meerdere PRs tegelijk open hebben?**
Ja. Elke PR krijgt een eigen preview pod op een unieke poort. Ze interfereren niet.

**Wat als de preview niet start?**
Check de CI logs in de PR. Mogelijke oorzaken:
- Dev Neo4j draait niet op Server A (port 7688)
- Server A heeft geen vrije resources
- Build fout in je code

**Kan ik `@claude` gebruiken in PR comments?**
Ja, als je lid bent van de organisatie. Typ `@claude` gevolgd door je vraag.
Externe contributors kunnen dit niet.

**Hoe test ik met een ander AI model?**
De preview pods gebruiken het productie Ollama model (Command-R). Als je een
ander model nodig hebt, overleg met Lukas over het gebruik van Server B of
het tijdelijk laden van een ander model.
