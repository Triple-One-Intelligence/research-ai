.PHONY: up down watch wui wapi wbeat clear deploy logs clean

# Where the final combined YAML will be written
BUNDLE_DEST  := /etc/research-ai/bundle.yaml

# Where the systemd unit file will be written
UNIT_DEST    := /etc/containers/systemd/research-ai.kube

# dev rules:
up:
	podman build -t research-ai-api:dev -f ./api/Containerfile .
	mkdir -p .caddy/data .caddy/config
	{ \
        cat kube/env.yaml; \
        echo "---"; \
        cat kube/pod-dev.yaml; \
    } | podman kube play -

down:
	{ \
        cat kube/env.yaml; \
        echo "---"; \
        cat kube/pod-dev.yaml; \
    } | podman kube down -

labelSELinux:
	sudo chcon -R -t container_file_t -l s0 frontend .
	sudo chcon -R -t container_file_t -l s0 api .
	sudo chcon -t container_file_t -l s0 caddy/Caddyfile.dev

watch:
	podman pod logs -f research-ai-dev

wapi:
	podman logs -f research-ai-dev-api

wbeat:
	podman logs -f research-ai-dev-surf-heartbeat

wui:
	podman logs -f research-ai-dev-frontend

clear:
	podman rm -f -a
	podman pod rm -f -a
	podman volume rm -f -a
	podman rmi -f -a


# prod rules:
deploy:
# build
	podman build -t research-ai-api:prod -f ./api/Containerfile .
	podman build -t research-ai-frontend:prod -f ./frontend/Containerfile .

# install quadlet units
	sudo mkdir -p /etc/containers/systemd
	sudo install -m 0644 -D kube/research-ai-prod.pod /etc/containers/systemd/research-ai-prod.pod
	sudo install -m 0644 -D kube/research-ai-api.container /etc/containers/systemd/research-ai-api.container
	sudo install -m 0644 -D kube/research-ai-frontend.container /etc/containers/systemd/research-ai-frontend.container
	sudo install -m 0644 -D kube/research-ai-ricgraph.container /etc/containers/systemd/research-ai-ricgraph.container

# install env file
	sudo mkdir -p /etc/research-ai
	sudo install -m 0644 -D kube/research-ai.env /etc/research-ai/research-ai.env

# volumes (PVC replacements) - idempotent
	podman volume create caddy-data || true
	podman volume create caddy-config || true
	podman volume create ricgraph-data || true

# reload + enable/start (pod pulls containers via Wants=; containers pull pod via Requires=)
	sudo systemctl daemon-reload
	sudo systemctl enable --now research-ai-prod-pod.service
	sudo systemctl enable --now research-ai-api.service
	sudo systemctl enable --now research-ai-frontend.service
	sudo systemctl enable --now research-ai-ricgraph.service


undeploy:
# stop + disable (ignore if not present)
	sudo systemctl disable --now research-ai-ricgraph.service 2>/dev/null || true
	sudo systemctl disable --now research-ai-frontend.service 2>/dev/null || true
	sudo systemctl disable --now research-ai-api.service 2>/dev/null || true
	sudo systemctl disable --now research-ai-prod-pod.service 2>/dev/null || true

# remove env file
	sudo rm -f /etc/research-ai/research-ai.env

# remove quadlet units
	sudo rm -f /etc/containers/systemd/research-ai-prod.pod
	sudo rm -f /etc/containers/systemd/research-ai-api.container
	sudo rm -f /etc/containers/systemd/research-ai-frontend.container
	sudo rm -f /etc/containers/systemd/research-ai-ricgraph.container

# reload
	sudo systemctl daemon-reload

logs:
	journalctl -fu research-ai

clean:
	sudo rm -f $(UNIT_DEST)
	sudo systemctl daemon-reload
	rm -f $(BUNDLE_DEST)
