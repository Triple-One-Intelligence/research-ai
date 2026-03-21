# CI/CD Setup — Nog te doen met repo admin (@jandre-d)

## Vereist: repo admin rechten

- [ ] **Self-hosted runner toevoegen** — Settings → Actions → Runners → New self-hosted runner
  - Linux / x64 selecteren
  - Token kopiëren en aan Lukas geven
  - Lukas installeert de runner op de server als systemd service
- [ ] **Branch protection op master** — Settings → Branches → Add rule voor `master`
  - [x] Require a pull request before merging (1 approval)
  - [x] Require status checks to pass (selecteer: `test-api`, `build-frontend`, `branch-name`)
  - [x] Dismiss stale pull request approvals when new commits are pushed
  - [x] Require branches to be up to date before merging
  - [x] Do not allow bypassing the above settings
- [ ] **Production environment aanmaken** — Settings → Environments → New environment
  - Naam: `production`
  - Required reviewers: @Lukasvd123 en/of @jandre-d
  - Deployment branches: alleen `master`
- [ ] **CodeQL aanzetten** — Settings → Code security → Enable CodeQL
- [ ] **Squash merge afdwingen** — Settings → General → Pull Requests
  - Allow squash merging: aan
  - Allow merge commits: uit
  - Allow rebase merging: uit
  - Default: squash merge
- [ ] **Auto-delete head branches** — Settings → General → Automatically delete head branches (aan)

## Vereist: Lukas op de server

- [ ] **Runner user aanmaken** op de productie server
  ```bash
  sudo useradd -m -s /bin/bash github-runner
  sudo loginctl enable-linger github-runner
  ```
- [ ] **Runner installeren** met het token van de admin
  ```bash
  sudo su - github-runner
  mkdir actions-runner && cd actions-runner
  # Download URL en token komen van GitHub UI
  curl -o actions-runner-linux-x64-2.XXX.X.tar.gz -L <URL>
  tar xzf ./actions-runner-linux-x64-2.XXX.X.tar.gz
  ./config.sh --url https://github.com/jandre-d/research-ai \
              --token <TOKEN> \
              --labels fedora,podman,production \
              --name research-ai-runner \
              --unattended
  ```
- [ ] **Runner als systemd service**
  ```bash
  exit  # terug naar sudo user
  cd /home/github-runner/actions-runner
  sudo ./svc.sh install github-runner
  sudo ./svc.sh start
  ```
- [ ] **Verifiëren** dat runner groen is in GitHub Settings → Actions → Runners

## Al gedaan (in deze branch)

- [x] CI workflow: unit tests + frontend build + branch name validatie
- [x] CI workflow: integration tests op self-hosted runner (push to master)
- [x] CI workflow: auto-deploy met environment approval gate
- [x] Dependabot configuratie (Python, npm, GitHub Actions — wekelijks)
- [x] CODEOWNERS voor automatische reviewer toewijzing
- [x] PR template geüpdatet met CI checklist
- [x] PR auto-populate: YouTrack link automatisch invullen op basis van branch naam
- [x] Branch naming conventie check (feat/, fix/, test/, docs/, refactor/)
