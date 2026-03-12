# research-ai Makefile — run `make help` for available targets
# ─────────────────────────────────────────────────────────────────────────────

.PHONY: help dev up down tunnel tunnel-stop tunnel-status \
        watch wapi wui test test-unit test-dev test-deploy \
        enrich enrich-force harvest deploy undeploy dev-env-info \
        neo4j-backup neo4j-restore \
        logs logs-api logs-ui logs-ric labelSELinux setup-wsl-ssh nuke

# ── Config ───────────────────────────────────────────────────────────────────

# Strip \r from env files (users on Windows may save with CRLF)
_load_env = if [ -f $(1) ]; then sed -i 's/\r$$//' $(1); set -a; . $(1); set +a; fi

REMOTE_SERVER ?= $(shell grep -s '^REMOTE_SERVER=' kube/research-ai-dev.env | tr -d '\r' | cut -d= -f2-)
REMOTE_SERVER := $(or $(REMOTE_SERVER),root@0xai.nl)

_G := \033[32m
_Y := \033[33m
_R := \033[31m
_C := \033[36m
_B := \033[1m
_0 := \033[0m

UNIT_TESTS := tests/test_query_utils.py tests/test_database_utils.py \
              tests/test_autocomplete_utils.py tests/test_enrich.py \
              tests/test_schemas.py tests/test_api_endpoints.py \
              tests/test_connections_endpoint.py

DEV_TESTS  := tests/test_smoke_dev.py tests/test_integration_api.py

# ── Help ─────────────────────────────────────────────────────────────────────

help:
	@printf "$(_B)research-ai$(_0) — dev & deploy toolkit\n\n"
	@printf "$(_C)Development$(_0)\n"
	@echo "  dev              Full dev env (tunnel + pod + tests)"
	@echo "  up / down        Start / stop dev pod"
	@echo "  tunnel           SSH tunnel to prod services"
	@echo "  tunnel-stop      Stop SSH tunnel"
	@echo "  tunnel-status    Check tunnel status"
	@echo "  watch            Tail all container logs"
	@echo "  wapi / wui       Tail API / frontend logs"
	@printf "\n$(_C)Testing$(_0)\n"
	@echo "  test             Unit + dev integration tests"
	@echo "  test-unit        Unit tests only (offline)"
	@echo "  test-dev         Dev smoke + integration (needs make dev)"
	@echo "  test-deploy      Prod smoke tests (run on server)"
	@printf "\n$(_C)Data$(_0)\n"
	@echo "  enrich           Enrich publications (abstracts + embeddings)"
	@echo "  enrich-force     Re-enrich all publications"
	@echo "  harvest          Run ricgraph harvesting"
	@echo "  neo4j-backup     Backup Neo4j database to /var/backups/research-ai/"
	@echo "  neo4j-restore    Restore Neo4j database from latest backup"
	@printf "\n$(_C)Production$(_0)\n"
	@echo "  deploy           Build + deploy to production"
	@echo "  undeploy         Stop + remove all prod services"
	@echo "  dev-env-info     Print dev env config for this server"
	@echo "  logs             Tail all prod logs"
	@printf "\n$(_C)Setup$(_0)\n"
	@echo "  setup-wsl-ssh    Symlink Windows SSH keys into WSL"
	@echo "  labelSELinux     SELinux relabel (Fedora/RHEL)"
	@printf "\n$(_R)Danger$(_0)\n"
	@echo "  nuke             Destroy ALL containers, pods, volumes, images"
	@echo ""

# ── Auto-install prerequisites (called automatically) ─────────────────────

define _ensure_deps
	@MISSING=""; \
	for cmd in podman ssh nc envsubst; do \
		command -v $$cmd >/dev/null 2>&1 || MISSING="$$MISSING $$cmd"; \
	done; \
	if [ -n "$$MISSING" ]; then \
		if command -v apt-get >/dev/null 2>&1; then \
			printf "$(_C)[setup]$(_0) Installing:$$MISSING\n"; \
			PKGS=""; \
			for cmd in $$MISSING; do \
				case $$cmd in \
					podman)   PKGS="$$PKGS podman" ;; \
					ssh)      PKGS="$$PKGS openssh-client" ;; \
					nc)       PKGS="$$PKGS netcat-openbsd" ;; \
					envsubst) PKGS="$$PKGS gettext-base" ;; \
				esac; \
			done; \
			sudo apt-get update -qq && sudo apt-get install -yqq $$PKGS; \
		elif command -v dnf >/dev/null 2>&1; then \
			printf "$(_C)[setup]$(_0) Installing:$$MISSING\n"; \
			PKGS=""; \
			for cmd in $$MISSING; do \
				case $$cmd in \
					podman)   PKGS="$$PKGS podman" ;; \
					ssh)      PKGS="$$PKGS openssh-clients" ;; \
					nc)       PKGS="$$PKGS nmap-ncat" ;; \
					envsubst) PKGS="$$PKGS gettext" ;; \
				esac; \
			done; \
			sudo dnf install -yq $$PKGS; \
		else \
			printf "$(_R)[setup]$(_0) Missing:$$MISSING — install them manually\n"; \
			exit 1; \
		fi; \
	fi
endef

# ── Test image (built from API image + pytest) ────────────────────────────

TEST_IMG := research-ai-test:dev
TEST_RUN := podman run --rm -t --network host -v ./api:/work:ro -e FORCE_COLOR=1 $(TEST_IMG)

.PHONY: test-image
test-image:
	@podman build -t research-ai-api:dev -f ./api/Containerfile . -q
	@podman build -t $(TEST_IMG) -f ./api/Containerfile.test . -q

# ── Development ──────────────────────────────────────────────────────────────

dev: down
	$(_ensure_deps)
	@printf "\n$(_B)Starting dev environment...$(_0)\n\n"
	@$(MAKE) -s tunnel &
	@printf "$(_C)[dev]$(_0) Waiting for SSH tunnel...\n"
	@for i in $$(seq 1 30); do nc -z localhost 7687 2>/dev/null && break || sleep 1; done
	@nc -z localhost 7687 2>/dev/null \
		&& printf "$(_G)[dev]$(_0) Tunnel up\n" \
		|| { printf "$(_R)[dev]$(_0) Tunnel failed. Try: ssh $(REMOTE_SERVER) echo ok\n"; exit 1; }
	@$(MAKE) -s up
	@printf "$(_C)[dev]$(_0) Waiting for frontend (Vite)...\n"
	@for i in $$(seq 1 60); do nc -z localhost 5173 2>/dev/null && break || sleep 1; done
	@nc -z localhost 5173 2>/dev/null \
		&& printf "$(_G)[dev]$(_0) Frontend ready\n" \
		|| printf "$(_Y)[dev]$(_0) Frontend not ready yet (tests may fail)\n"
	@printf "\n$(_G)$(_B)  Dev running!$(_0)  https://localhost:3000\n\n"
	@$(MAKE) -s test || printf "\n$(_Y)[dev]$(_0) Some tests failed (see above)\n\n"

up:
	$(_ensure_deps)
	@printf "$(_C)[up]$(_0) Building API...\n"
	@podman build -t research-ai-api:dev -f ./api/Containerfile . -q
	@mkdir -p .caddy/data .caddy/config
	@printf "$(_C)[up]$(_0) Starting pod...\n"
	@$(call _load_env,./kube/research-ai-dev.env); \
		envsubst < kube/pod-dev.yaml | podman kube play - >/dev/null
	@printf "$(_G)[up]$(_0) Pod started\n"

down:
	@-pkill -f 'ssh -N.*$(REMOTE_SERVER)' 2>/dev/null || true
	@$(call _load_env,./kube/research-ai-dev.env); \
		envsubst < kube/pod-dev.yaml | podman kube down - 2>/dev/null || true

# ── SSH Tunnel ───────────────────────────────────────────────────────────────

setup-wsl-ssh:
	@bash scripts/setup-wsl-ssh.sh

tunnel: setup-wsl-ssh
	@printf "$(_C)[tunnel]$(_0) Connecting to $(REMOTE_SERVER)...\n"
	@$(call _load_env,./kube/research-ai-dev.env); \
	ssh -N -o ExitOnForwardFailure=yes -o ConnectTimeout=10 \
		-o ServerAliveInterval=30 -o ServerAliveCountMax=3 \
		-L 7687:localhost:7687  -L 7474:localhost:7474 \
		-L 18080:localhost:8080 -L 3030:localhost:3030 \
		-L 11434:localhost:11434 $$REMOTE_SERVER 2>&1 \
	|| { printf "$(_R)[tunnel]$(_0) Failed. Try: ssh $(REMOTE_SERVER) echo ok\n"; exit 1; }

tunnel-stop:
	@PIDS=$$(pgrep -f "ssh.*-N.*$(REMOTE_SERVER)" 2>/dev/null); \
	[ -n "$$PIDS" ] \
		&& kill $$PIDS && printf "$(_G)[tunnel]$(_0) Stopped\n" \
		|| printf "$(_Y)[tunnel]$(_0) Not running\n"

tunnel-status:
	@PIDS=$$(pgrep -f "ssh.*-N.*$(REMOTE_SERVER)" 2>/dev/null); \
	[ -n "$$PIDS" ] \
		&& printf "$(_G)[tunnel]$(_0) Running (PID $$PIDS)\n" \
		|| printf "$(_R)[tunnel]$(_0) Not running\n"

# ── Testing ──────────────────────────────────────────────────────────────────

test: test-image
	@printf "\n$(_B)═══ Unit Tests ═══$(_0)\n\n"
	@$(TEST_RUN) python -m pytest $(UNIT_TESTS) -v --tb=short --color=yes; U=$$?; \
	printf "\n$(_B)═══ Integration Tests ═══$(_0)\n(skips if dev pod not running)\n\n"; \
	$(TEST_RUN) python -m pytest $(DEV_TESTS) -v --tb=short --color=yes; D=$$?; \
	printf "\n$(_B)═══ Summary ═══$(_0)\n"; \
	[ $$U -eq 0 ] && printf "  $(_G)Unit:        PASS$(_0)\n" || printf "  $(_R)Unit:        FAIL$(_0)\n"; \
	[ $$D -eq 0 ] && printf "  $(_G)Integration: PASS$(_0)\n" \
		|| { [ $$D -eq 5 ] && printf "  $(_Y)Integration: SKIP$(_0)\n" || printf "  $(_R)Integration: FAIL$(_0)\n"; }; \
	printf "\n  $(_C)URL$(_0)  https://localhost:3000\n\n"; \
	exit $$U

test-unit: test-image
	@$(TEST_RUN) python -m pytest $(UNIT_TESTS) -v --tb=short --color=yes

test-dev: test-image
	@$(TEST_RUN) python -m pytest $(DEV_TESTS) -v --tb=short --color=yes

test-deploy: test-image
	@$(call _load_env,./kube/research-ai-prod.env); \
	podman run --rm -t --network host -v ./api:/work:ro -e FORCE_COLOR=1 \
		-e CADDY_HOSTNAME=$$CADDY_HOSTNAME -e VERIFY_SSL=false \
		-e REMOTE_NEO4J_USER=$$REMOTE_NEO4J_USER -e REMOTE_NEO4J_PASS=$$REMOTE_NEO4J_PASS \
		$(TEST_IMG) python -m pytest tests/test_smoke_deploy.py -v --tb=short --color=yes

# ── Data ─────────────────────────────────────────────────────────────────────

enrich:
	podman exec research-ai-api python -m app.scripts.enrich

enrich-force:
	podman exec research-ai-api python -m app.scripts.enrich --force

harvest:
	podman exec research-ai-ricgraph make run_bash_script

NEO4J_BACKUP_DIR := /var/backups/research-ai

neo4j-backup:
	@mkdir -p $(NEO4J_BACKUP_DIR)
	@printf "$(_B)Stopping Neo4j for backup...$(_0)\n"
	systemctl stop research-ai-neo4j.service
	podman run --rm --entrypoint "" \
		-v neo4j-data:/data:ro \
		-v $(NEO4J_BACKUP_DIR):/backup \
		docker.io/library/neo4j:5 \
		bash -c "cp -a /data/. /backup/neo4j-data/"
	systemctl start research-ai-neo4j.service
	@ls -sh $(NEO4J_BACKUP_DIR)/neo4j-data/ | head -1
	@printf "$(_G)[neo4j-backup]$(_0) Saved to $(NEO4J_BACKUP_DIR)/neo4j-data/\n"

neo4j-restore:
	@if [ ! -d $(NEO4J_BACKUP_DIR)/neo4j-data ]; then \
		printf "$(_R)No backup found at $(NEO4J_BACKUP_DIR)/neo4j-data/$(_0)\n"; exit 1; \
	fi
	@printf "$(_B)Stopping Neo4j for restore...$(_0)\n"
	systemctl stop research-ai-neo4j.service
	podman run --rm --entrypoint "" \
		-v neo4j-data:/data \
		-v $(NEO4J_BACKUP_DIR):/backup:ro \
		docker.io/library/neo4j:5 \
		bash -c "rm -rf /data/* && cp -a /backup/neo4j-data/. /data/"
	systemctl start research-ai-neo4j.service
	@printf "$(_G)[neo4j-restore]$(_0) Restored from $(NEO4J_BACKUP_DIR)/neo4j-data/\n"

# ── Logs ─────────────────────────────────────────────────────────────────────

watch:
	podman pod logs -f research-ai-dev
wapi:
	podman logs -f research-ai-dev-api
wui:
	podman logs -f research-ai-dev-frontend
logs:
	journalctl -f -u research-ai-api -u research-ai-frontend -u research-ai-ricgraph
logs-api:
	journalctl -u research-ai-api -f
logs-ui:
	journalctl -u research-ai-frontend -f
logs-ric:
	journalctl -u research-ai-ricgraph -f

# ── Production ───────────────────────────────────────────────────────────────

deploy:
	@printf "$(_B)Deploying...$(_0)\n"
	podman build -t research-ai-api:prod -f ./api/Containerfile .
	$(call _load_env,./kube/research-ai-prod.env); \
		podman build -t research-ai-frontend:prod -f ./frontend/Containerfile . \
		--build-arg VITE_API_URL=$$VITE_API_URL
	mkdir -p /etc/containers/systemd /etc/research-ai
	install -m 0644 kube/research-ai-net.network      /etc/containers/systemd/
	install -m 0644 kube/research-ai-frontend.container /etc/containers/systemd/
	install -m 0644 kube/research-ai-api.container     /etc/containers/systemd/
	install -m 0644 kube/research-ai-ricgraph.container /etc/containers/systemd/
	install -m 0644 kube/research-ai-neo4j.container   /etc/containers/systemd/
	install -m 0644 kube/research-ai-ai.container      /etc/containers/systemd/
	install -m 0644 kube/research-ai-prod.env          /etc/research-ai/
	$(call _load_env,./kube/research-ai-prod.env); \
		envsubst < kube/ricgraph.ini > /etc/research-ai/ricgraph.ini && chmod 0640 /etc/research-ai/ricgraph.ini
	podman network create research-ai-net --subnet=10.89.0.0/24 --gateway=10.89.0.1 2>/dev/null || true
	podman volume create caddy-data 2>/dev/null || true
	podman volume create caddy-config 2>/dev/null || true
	podman volume create neo4j-data 2>/dev/null || true
	podman volume create ai-data 2>/dev/null || true
	systemctl daemon-reload
	systemctl restart --now research-ai-neo4j.service
	systemctl restart --now research-ai-ai.service
	systemctl restart --now research-ai-ricgraph.service
	systemctl restart --now research-ai-api.service
	systemctl restart --now research-ai-frontend.service
	@printf "$(_C)[deploy]$(_0) Pulling AI models...\n"
	@$(call _load_env,./kube/research-ai-prod.env); \
	for i in 1 2 3 4 5; do curl -sf http://127.0.0.1:11434/api/tags >/dev/null && break || sleep 5; done; \
	curl -sf http://127.0.0.1:11434/api/pull -d "{\"name\":\"$$EMBED_MODEL\"}" | tail -1; \
	curl -sf http://127.0.0.1:11434/api/pull -d "{\"name\":\"$$CHAT_MODEL\"}" | tail -1
	@printf "$(_G)[deploy]$(_0) Done.\n"
	@$(MAKE) -s dev-env-info

undeploy:
	-systemctl stop research-ai-{frontend,api,ricgraph,neo4j,ai,net-network}.service 2>/dev/null
	rm -f /etc/research-ai/research-ai-prod.env
	rm -f /etc/containers/systemd/research-ai-{net.network,frontend,api,ricgraph,neo4j,ai}.container
	systemctl daemon-reload

dev-env-info:
	@bash scripts/dev-env-info.sh

# ── Setup ────────────────────────────────────────────────────────────────────

labelSELinux:
	sudo chcon -R -t container_file_t -l s0 frontend api .
	sudo chcon -t container_file_t -l s0 caddy/Caddyfile.dev

nuke:
	@printf "$(_R)$(_B)WARNING: destroys ALL containers, pods, volumes, images!$(_0)\n"
	@printf "Ctrl+C within 5s to cancel...\n" && sleep 5
	-podman ps -aq       | xargs -r podman rm -f
	-podman pod ps -q    | xargs -r podman pod rm -f
	-podman volume ls -q | xargs -r podman volume rm -f
	-podman images -aq   | xargs -r podman rmi -f
	podman system prune -a -f --volumes
