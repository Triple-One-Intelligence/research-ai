.PHONY: all dev up down nuke labelSELinux watch wapi wui \
        deploy undeploy ci-deploy \
        logs logs-api logs-ui logs-ric \
        enrich enrich-force harvest \
        neo4j-backup neo4j-restore \
        tunnel tunnel-ui \
        test test-unit test-dev test-deploy test-image

REMOTE_SERVER    ?= root@0xai.nl
NEO4J_BACKUP_DIR := /var/backups/research-ai

UNIT_TESTS   := tests/unit/
DEV_TESTS    := tests/integration/ tests/system/test_smoke_dev.py
DEPLOY_TESTS := tests/system/test_smoke_deploy.py


TEST_IMG := research-ai-test:dev
TEST_RUN := podman run --rm -t --network host -v ./api:/work:ro $(TEST_IMG)


all:
	@printf "Usage: make <target>\n\
\n\
dev\n\
  up            build and start the dev pod\n\
  down          stop the dev pod\n\
  tunnel        open SSH tunnel to $(REMOTE_SERVER) (blocking)\n\
  tunnel-ui     tunnel the UI to localhost:8080\n\
  dev           up + tunnel\n\
  watch         tail all dev pod logs\n\
  wapi          tail api logs\n\
  wui           tail frontend logs\n\
  labelSELinux  relabel files for SELinux container access\n\
\n\
data\n\
  enrich        run enrichment script\n\
  enrich-force  run enrichment script (force re-enrich)\n\
  harvest       run ricgraph harvest\n\
  neo4j-backup  backup neo4j data to $(NEO4J_BACKUP_DIR)\n\
  neo4j-restore restore neo4j data from $(NEO4J_BACKUP_DIR)\n\
\n\
prod\n\
  deploy        full production deploy (build, install, start, pull models)\n\
  ci-deploy     partial deploy for CI (api + frontend only)\n\
  undeploy      stop and remove all production services\n\
  logs          tail api + frontend + ricgraph logs\n\
  logs-api      tail api logs\n\
  logs-ui       tail frontend logs\n\
  logs-ric      tail ricgraph logs\n\
\n\
test\n\
  test          unit tests + dev integration tests\n\
  test-unit     unit tests only (no services needed)\n\
  test-dev      dev smoke + integration tests (requires: make dev)\n\
  test-deploy   prod deployment tests (run on prod server)\n\
  test-image    build test container images\n\
\n\
misc\n\
  nuke          wipe all containers, pods, volumes, and images\n"


# --- dev ---

up:
	podman build -t research-ai-api:dev -f ./api/Containerfile .
	mkdir -p .caddy/data .caddy/config
	set -a; . ./kube/research-ai-dev.env; set +a; \
	envsubst < kube/pod-dev.yaml | podman kube play -

down:
	set -a; . ./kube/research-ai-dev.env; set +a; \
	envsubst < kube/pod-dev.yaml | podman kube down - 2>/dev/null || true

# Tunnels: Neo4j Bolt (7687), Neo4j HTTP (7474), Ricgraph Explorer (3030), Ollama (11434)
tunnel:
	ssh -N \
	    -L 7687:localhost:7687 \
	    -L 7474:localhost:7474 \
	    -L 3030:localhost:3030 \
	    -L 11434:localhost:11434 \
	    $(REMOTE_SERVER)

# Tunnels the frontend (8080) to localhost for local access
tunnel-ui:
	ssh -N \
	    -L 8080:localhost:8080 \
	    $(REMOTE_SERVER)

dev: up tunnel

labelSELinux:
	sudo chcon -R -t container_file_t -l s0 frontend api .
	sudo chcon -t container_file_t -l s0 caddy/Caddyfile.dev

watch:
	podman pod logs -f research-ai-dev

wapi:
	podman logs -f research-ai-dev-api

wui:
	podman logs -f research-ai-dev-frontend


# --- data ---

enrich:
	podman exec research-ai-api python -m app.scripts.enrich

enrich-force:
	podman exec research-ai-api python -m app.scripts.enrich --force

harvest:
	podman exec research-ai-ricgraph make run_bash_script

neo4j-backup:
	mkdir -p $(NEO4J_BACKUP_DIR)
	systemctl stop research-ai-neo4j.service
	podman run --rm --entrypoint "" \
	    -v neo4j-data:/data:ro \
	    -v $(NEO4J_BACKUP_DIR):/backup \
	    docker.io/library/neo4j:5 \
	    bash -c "cp -a /data/. /backup/neo4j-data/"
	systemctl start research-ai-neo4j.service

neo4j-restore:
	@if [ ! -d $(NEO4J_BACKUP_DIR)/neo4j-data ]; then \
	    echo "No backup found at $(NEO4J_BACKUP_DIR)/neo4j-data/"; exit 1; \
	fi
	systemctl stop research-ai-neo4j.service
	podman run --rm --entrypoint "" \
	    -v neo4j-data:/data \
	    -v $(NEO4J_BACKUP_DIR):/backup:ro \
	    docker.io/library/neo4j:5 \
	    bash -c "rm -rf /data/* && cp -a /backup/neo4j-data/. /data/"
	systemctl start research-ai-neo4j.service


# --- prod ---

deploy:
	podman build -t research-ai-api:prod -f ./api/Containerfile .
	set -a; . ./kube/research-ai-prod.env; set +a; \
	podman build -t research-ai-frontend:prod -f ./frontend/Containerfile .

	mkdir -p /etc/containers/systemd /etc/research-ai
	install -m 0644 kube/research-ai-net.network         /etc/containers/systemd/
	install -m 0644 kube/research-ai-frontend.container  /etc/containers/systemd/
	install -m 0644 kube/research-ai-api.container       /etc/containers/systemd/
	install -m 0644 kube/research-ai-ricgraph.container  /etc/containers/systemd/
	install -m 0644 kube/research-ai-neo4j.container     /etc/containers/systemd/
	install -m 0644 kube/research-ai-ai.container        /etc/containers/systemd/
	install -m 0644 kube/research-ai-prod.env            /etc/research-ai/
	set -a; . ./kube/research-ai-prod.env; set +a; \
	envsubst < kube/ricgraph.ini > /etc/research-ai/ricgraph.ini && chmod 0640 /etc/research-ai/ricgraph.ini

	podman network create research-ai-net --subnet=10.89.0.0/24 --gateway=10.89.0.1 2>/dev/null || true
	podman volume create caddy-data   2>/dev/null || true
	podman volume create caddy-config 2>/dev/null || true
	podman volume create neo4j-data   2>/dev/null || true
	podman volume create ai-data      2>/dev/null || true

	systemctl daemon-reload
	systemctl restart --now research-ai-neo4j.service
	systemctl restart --now research-ai-ai.service
	systemctl restart --now research-ai-ricgraph.service
	systemctl restart --now research-ai-api.service
	systemctl restart --now research-ai-frontend.service

	# Wait for Ollama to come up, then pull the embed and chat models listed in the env file
	@set -a; . ./kube/research-ai-prod.env; set +a; \
	for i in 1 2 3 4 5; do curl -sf http://127.0.0.1:11434/api/tags >/dev/null && break || sleep 5; done; \
	for model in $$EMBED_MODEL $$CHAT_MODEL; do \
	    echo "  pulling $$model..."; \
	    curl -sf http://127.0.0.1:11434/api/pull -d "{\"name\":\"$$model\"}" | tail -1; \
	done

ci-deploy:
	podman build -t research-ai-api:prod -f ./api/Containerfile .
	set -a; . ./kube/research-ai-prod.env; set +a; \
	podman build -t research-ai-frontend:prod -f ./frontend/Containerfile .
	sudo install -m 0644 kube/research-ai-frontend.container /etc/containers/systemd/
	sudo install -m 0644 kube/research-ai-api.container      /etc/containers/systemd/
	sudo systemctl daemon-reload
	sudo systemctl restart research-ai-api.service
	sudo systemctl restart research-ai-frontend.service

undeploy:
	-systemctl stop research-ai-frontend.service 2>/dev/null || true
	-systemctl stop research-ai-api.service 2>/dev/null || true
	-systemctl stop research-ai-ricgraph.service 2>/dev/null || true
	-systemctl stop research-ai-neo4j.service 2>/dev/null || true
	-systemctl stop research-ai-ai.service 2>/dev/null || true
	-systemctl stop research-ai-net-network.service 2>/dev/null || true
	rm -f /etc/research-ai/research-ai-prod.env
	rm -f /etc/containers/systemd/research-ai-net.network
	rm -f /etc/containers/systemd/research-ai-frontend.container
	rm -f /etc/containers/systemd/research-ai-api.container
	rm -f /etc/containers/systemd/research-ai-ricgraph.container
	rm -f /etc/containers/systemd/research-ai-neo4j.container
	rm -f /etc/containers/systemd/research-ai-ai.container
	systemctl daemon-reload

logs:
	journalctl -f \
	    -u research-ai-api.service \
	    -u research-ai-frontend.service \
	    -u research-ai-ricgraph.service

logs-api:
	journalctl -u research-ai-api.service -f

logs-ui:
	journalctl -u research-ai-frontend.service -f

logs-ric:
	journalctl -u research-ai-ricgraph.service -f


# --- test ---

test-image:
	podman build -t research-ai-api:dev -f ./api/Containerfile . -q
	podman build -t $(TEST_IMG) -f ./api/Containerfile.test . -q

test-unit: test-image
	$(TEST_RUN) python -m pytest $(UNIT_TESTS) -v --tb=short

test-dev: test-image
	$(TEST_RUN) python -m pytest $(DEV_TESTS) -v --tb=long

test-deploy: test-image
	set -a; . ./kube/research-ai-prod.env; set +a; \
	podman run --rm -t --network host -v ./api:/work:ro \
	    -e REMOTE_NEO4J_USER=$$REMOTE_NEO4J_USER -e REMOTE_NEO4J_PASS=$$REMOTE_NEO4J_PASS \
	    $(TEST_IMG) python -m pytest $(DEPLOY_TESTS) -v --tb=short

test: test-unit
	@echo ""
	@echo "=== Unit tests passed. Running dev integration tests... ==="
	@echo "(tests will skip automatically if the dev pod is not running)"
	@echo ""
	$(TEST_RUN) python -m pytest $(DEV_TESTS) -v --tb=long


# --- misc ---

nuke:
	-podman ps -aq | xargs -r podman rm -f
	-podman pod ps -q | xargs -r podman pod rm -f
	-podman volume ls -q | xargs -r podman volume rm -f
	-podman images -aq | xargs -r podman rmi -f
	podman system prune -a -f --volumes
