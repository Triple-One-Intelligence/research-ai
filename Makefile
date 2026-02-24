.PHONY: up down nuke labelSELinux watch wapi wui deploy undeploy logs logs-api logs-ui logs-ric

# THE NUCLEAR OPTION:
# Wipes all containers, pods, volumes, and images from the system.
nuke:
	-podman ps -aq | xargs -r podman rm -f
	-podman pod ps -q | xargs -r podman pod rm -f
	-podman volume ls -q | xargs -r podman volume rm -f
	-podman images -aq | xargs -r podman rmi -f
	podman system prune -a -f --volumes

# dev rules:
up:
	podman build -t research-ai-api:dev -f ./api/Containerfile .
	mkdir -p .caddy/data .caddy/config
	set -a; . ./kube/research-ai.env; set +a; \
	envsubst < kube/pod-dev.yaml | podman kube play -

down:
	set -a; . ./kube/research-ai.env; set +a; \
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

# prod rules:
deploy:
	podman build -t research-ai-api:prod -f ./api/Containerfile .
	podman build -t research-ai-frontend:prod -f ./frontend/Containerfile .
	podman build -t research-ai-ricgraph:prod -f ./ricgraph/Containerfile .

	mkdir -p /etc/containers/systemd
	install -m 0644 -D kube/research-ai-api.container /etc/containers/systemd/research-ai-api.container
	install -m 0644 -D kube/research-ai-frontend.container /etc/containers/systemd/research-ai-frontend.container
	install -m 0644 -D kube/research-ai-ricgraph.container /etc/containers/systemd/research-ai-ricgraph.container

	mkdir -p /etc/research-ai
	install -m 0644 -D kube/research-ai.env /etc/research-ai/research-ai.env

	podman volume create caddy-data || true
	podman volume create caddy-config || true
	podman volume create ricgraph-data || true

	systemctl daemon-reload
	systemctl restart --now research-ai-frontend.service
	systemctl restart --now research-ai-api.service
	systemctl restart --now research-ai-ricgraph.service

undeploy:
	systemctl stop research-ai-ricgraph.service 2>/dev/null || true
	systemctl stop research-ai-api.service 2>/dev/null || true
	systemctl stop research-ai-frontend.service 2>/dev/null || true

	rm -f /etc/research-ai/research-ai.env

	rm -f /etc/containers/systemd/research-ai-api.container
	rm -f /etc/containers/systemd/research-ai-frontend.container
	rm -f /etc/containers/systemd/research-ai-ricgraph.container

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
