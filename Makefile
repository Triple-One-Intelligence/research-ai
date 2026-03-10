.PHONY: dev up down nuke labelSELinux watch wapi wui deploy undeploy logs logs-api logs-ui logs-ric enrich enrich-force harvest tunnel tunnel-stop tunnel-status setup-wsl-ssh test test-unit test-dev test-deploy

REMOTE_SERVER ?= root@0xai.nl

# THE NUCLEAR OPTION:
# Wipes all containers, pods, volumes, and images from the system.
nuke:
	-podman ps -aq | xargs -r podman rm -f
	-podman pod ps -q | xargs -r podman pod rm -f
	-podman volume ls -q | xargs -r podman volume rm -f
	-podman images -aq | xargs -r podman rmi -f
	podman system prune -a -f --volumes

# dev rules:

# Symlink Windows SSH keys into WSL if running under WSL and ~/.ssh is missing
setup-wsl-ssh:
	@if grep -qi microsoft /proc/version 2>/dev/null; then \
		WIN_USER=$$(cmd.exe /C "echo %USERNAME%" 2>/dev/null | tr -d '\r'); \
		WIN_SSH="/mnt/c/Users/$$WIN_USER/.ssh"; \
		if [ ! -d "$$HOME/.ssh" ] && [ -d "$$WIN_SSH" ]; then \
			ln -s "$$WIN_SSH" "$$HOME/.ssh"; \
			echo "Linked $$WIN_SSH -> $$HOME/.ssh"; \
		elif [ -d "$$HOME/.ssh" ]; then \
			echo "$$HOME/.ssh already exists, skipping symlink"; \
		else \
			echo "Windows SSH keys not found at $$WIN_SSH"; \
		fi; \
	else \
		echo "Not running in WSL, skipping SSH key setup"; \
	fi

tunnel: setup-wsl-ssh
	set -a; . ./kube/research-ai-dev.env; set +a; \
	ssh -N -o ExitOnForwardFailure=yes \
		-L 7687:localhost:7687 \
		-L 7474:localhost:7474 \
		-L 18080:localhost:8080 \
		-L 3030:localhost:3030 \
		-L 11434:localhost:11434 \
		$$REMOTE_SERVER \
	&& echo "[tunnel] SSH tunnel running in background (PID $$(pgrep -f 'ssh -f -N.*$$REMOTE_SERVER' | tail -1))" \
	|| (echo "[tunnel] ERROR: Failed to establish SSH tunnel. Is the remote server reachable?" && exit 1)

tunnel-stop:
	@set -a; . ./kube/research-ai-dev.env; set +a; \
	PIDS=$$(pgrep -f "ssh -f -N.*$$REMOTE_SERVER" 2>/dev/null); \
	if [ -n "$$PIDS" ]; then \
		kill $$PIDS && echo "[tunnel] Stopped SSH tunnel (PID $$PIDS)"; \
	else \
		echo "[tunnel] No active tunnel found."; \
	fi

tunnel-status:
	@set -a; . ./kube/research-ai-dev.env; set +a; \
	PIDS=$$(pgrep -f "ssh -f -N.*$$REMOTE_SERVER" 2>/dev/null); \
	if [ -n "$$PIDS" ]; then \
		echo "[tunnel] Running (PID $$PIDS)"; \
	else \
		echo "[tunnel] Not running"; \
	fi

up:
	podman build -t research-ai-api:dev -f ./api/Containerfile .
	mkdir -p .caddy/data .caddy/config
	set -a; . ./kube/research-ai-dev.env; set +a; \
	envsubst < kube/pod-dev.yaml | podman kube play -

dev: down
	@$(MAKE) tunnel &
	@echo "  Waiting for SSH tunnel..."
	@for i in $$(seq 1 30); do nc -z localhost 7687 2>/dev/null && break || sleep 1; done
	@nc -z localhost 7687 2>/dev/null || { echo "  Tunnel failed to start"; exit 1; }
	@$(MAKE) up
	@echo ""
	@echo "  research-ai dev is running at: http://localhost:3000"
	@echo "  SSH tunnel to prod server running in background (PID $$!)"
	@echo ""
	@echo "  make watch  - view all logs"
	@echo "  make down   - stop the pod"
	@echo ""

down:
	-pkill -f 'ssh -N.*$(REMOTE_SERVER)' 2>/dev/null || true
	set -a; . ./kube/research-ai-dev.env; set +a; \
	envsubst < kube/pod-dev.yaml | podman kube down -

# relabel files to allow mapping to containers.
# only for development on OSes running a security-hardened Linux kernel
labelSELinux:
	sudo chcon -R -t container_file_t -l s0 frontend .
	sudo chcon -R -t container_file_t -l s0 api .
	sudo chcon -t container_file_t -l s0 caddy/Caddyfile.dev

watch:
	podman pod logs -f research-ai-dev

wapi:
	podman logs -f research-ai-dev-api

wui:
	podman logs -f research-ai-dev-frontend

enrich:
	podman exec research-ai-api python -m app.scripts.enrich

enrich-force:
	podman exec research-ai-api python -m app.scripts.enrich --force

harvest:
	podman exec research-ai-ricgraph make run_bash_script

# prod rules:
deploy:
	podman build -t research-ai-api:prod -f ./api/Containerfile .

	set -a; . ./kube/research-ai-prod.env; set +a; \
	podman build -t research-ai-frontend:prod -f ./frontend/Containerfile . --build-arg VITE_API_URL=$$VITE_API_URL

	mkdir -p /etc/containers/systemd
	install -m 0644 -D kube/research-ai-net.network /etc/containers/systemd/research-ai-net.network
	install -m 0644 -D kube/research-ai-frontend.container /etc/containers/systemd/research-ai-frontend.container
	install -m 0644 -D kube/research-ai-api.container /etc/containers/systemd/research-ai-api.container
	install -m 0644 -D kube/research-ai-ricgraph.container /etc/containers/systemd/research-ai-ricgraph.container
	install -m 0644 -D kube/research-ai-neo4j.container /etc/containers/systemd/research-ai-neo4j.container
	install -m 0644 -D kube/research-ai-ai.container /etc/containers/systemd/research-ai-ai.container

	mkdir -p /etc/research-ai
	install -m 0644 -D kube/research-ai-prod.env /etc/research-ai/research-ai-prod.env
	set -a; . ./kube/research-ai-prod.env; set +a; \
	envsubst < kube/ricgraph.ini > /etc/research-ai/ricgraph.ini && chmod 0640 /etc/research-ai/ricgraph.ini

	podman volume create caddy-data || true
	podman volume create caddy-config || true
	podman volume create neo4j-data || true
	podman volume create ai-data || true

	systemctl daemon-reload
	systemctl restart --now research-ai-net-network.service
	systemctl restart --now research-ai-neo4j.service
	systemctl restart --now research-ai-ai.service
	systemctl restart --now research-ai-ricgraph.service
	systemctl restart --now research-ai-api.service
	systemctl restart --now research-ai-frontend.service

	@echo "Services started. Enrich will run in background after startup..."
	@(sleep 30 && $(MAKE) enrich 2>&1 | tee enrich.log || echo "[enrich] FAILED" >> enrich.log &)

undeploy:
	systemctl stop research-ai-frontend.service 2>/dev/null || true
	systemctl stop research-ai-api.service 2>/dev/null || true
	systemctl stop research-ai-ricgraph.service 2>/dev/null || true
	systemctl stop research-ai-neo4j.service 2>/dev/null || true
	systemctl stop research-ai-ai.service 2>/dev/null || true
	systemctl stop research-ai-net-network.service 2>/dev/null || true

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

# test rules:

# Run all unit tests (no running services needed)
test-unit:
	cd api && pip install -q -r requirements-dev.txt && python -m pytest tests/test_query_utils.py tests/test_database_utils.py tests/test_autocomplete_utils.py tests/test_enrich.py tests/test_schemas.py tests/test_api_endpoints.py tests/test_connections_endpoint.py -v

# Run dev smoke + integration tests (requires: make dev + make tunnel)
test-dev:
	cd api && pip install -q -r requirements-dev.txt && python -m pytest tests/test_smoke_dev.py tests/test_integration_api.py -v --tb=long

# Run prod deployment tests (run ON the production server after make deploy)
test-deploy:
	cd api && pip install -q -r requirements-dev.txt && python -m pytest tests/test_smoke_deploy.py -v --tb=long

# Run everything: unit tests first, then dev integration if pod is running
test: test-unit
	@echo ""
	@echo "=== Unit tests passed. Running dev integration tests... ==="
	@echo "(tests will skip automatically if the dev pod is not running)"
	@echo ""
	-cd api && python -m pytest tests/test_smoke_dev.py tests/test_integration_api.py -v --tb=line
