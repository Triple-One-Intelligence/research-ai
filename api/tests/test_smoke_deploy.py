"""
Production deployment smoke tests.

These tests verify that a production deployment is fully operational:
- All systemd services are running
- The podman network exists
- All containers are healthy and responsive
- End-to-end request flow works (frontend → Caddy → API → Neo4j)
- SSL/TLS is configured

Run with: make test-deploy
Requires: `make deploy` to have been run on the production server.
Must be run ON the production server itself.
"""

import os
import subprocess
import socket
import pytest
import httpx

PROD_HOSTNAME = os.environ.get("PROD_HOSTNAME", "0xai.nl")
PROD_BASE_HTTP = f"http://{PROD_HOSTNAME}"
PROD_BASE_HTTPS = f"https://{PROD_HOSTNAME}"
TIMEOUT = 10.0
# Set VERIFY_SSL=true once TLS certificates are fully configured
VERIFY_SSL = os.environ.get("VERIFY_SSL", "false").lower() == "true"

SYSTEMD_SERVICES = [
    "research-ai-neo4j.service",
    "research-ai-ai.service",
    "research-ai-ricgraph.service",
    "research-ai-api.service",
    "research-ai-frontend.service",
]

CONTAINER_NAMES = [
    "research-ai-neo4j",
    "research-ai-ai",
    "research-ai-ricgraph",
    "research-ai-api",
    "research-ai-frontend",
]


def _run(cmd: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True, timeout=10)


def _service_active(name: str) -> bool:
    result = _run(["systemctl", "is-active", name])
    return result.stdout.strip() == "active"


def _container_running(name: str) -> bool:
    result = _run(["podman", "inspect", "--format", "{{.State.Status}}", name])
    return result.stdout.strip() == "running"


# ── Systemd Services ─────────────────────────────────────────────────────────

class TestSystemdServices:
    """Verify all systemd units are active."""

    @pytest.mark.parametrize("service", SYSTEMD_SERVICES)
    def test_service_is_active(self, service):
        result = _run(["systemctl", "is-active", service])
        status = result.stdout.strip()
        if status != "active":
            # Get recent logs for diagnosis
            log_result = _run(["journalctl", "-u", service, "-n", "20", "--no-pager"])
            pytest.fail(
                f"Service {service} is '{status}', expected 'active'.\n"
                f"Recent logs:\n{log_result.stdout}"
            )


# ── Podman Containers ────────────────────────────────────────────────────────

class TestPodmanContainers:
    """Verify all containers are running."""

    @pytest.mark.parametrize("container", CONTAINER_NAMES)
    def test_container_is_running(self, container):
        result = _run(["podman", "inspect", "--format", "{{.State.Status}}", container])
        status = result.stdout.strip()
        if status != "running":
            log_result = _run(["podman", "logs", "--tail", "30", container])
            pytest.fail(
                f"Container {container} is '{status}', expected 'running'.\n"
                f"Recent logs:\n{log_result.stdout}\n{log_result.stderr}"
            )

    def test_podman_network_exists(self):
        result = _run(["podman", "network", "inspect", "research-ai-net"])
        assert result.returncode == 0, (
            "Podman network 'research-ai-net' does not exist.\n"
            "Run: make deploy"
        )


# ── Network Connectivity ─────────────────────────────────────────────────────

class TestProdNetworkConnectivity:
    """Verify services are listening on expected ports."""

    def test_http_port_80(self):
        """Caddy should listen on port 80."""
        try:
            with socket.create_connection(("127.0.0.1", 80), timeout=3):
                pass
        except (ConnectionRefusedError, TimeoutError, OSError):
            pytest.fail(
                "Port 80 is not open.\n"
                "Check: systemctl status research-ai-frontend"
            )

    def test_https_port_443(self):
        """Caddy should listen on port 443."""
        try:
            with socket.create_connection(("127.0.0.1", 443), timeout=3):
                pass
        except (ConnectionRefusedError, TimeoutError, OSError):
            pytest.fail(
                "Port 443 is not open.\n"
                "Check: systemctl status research-ai-frontend"
            )

    def test_neo4j_internal_bolt(self):
        """Neo4j Bolt should be accessible on localhost:7687."""
        try:
            with socket.create_connection(("127.0.0.1", 7687), timeout=3):
                pass
        except (ConnectionRefusedError, TimeoutError, OSError):
            pytest.fail(
                "Neo4j Bolt port 7687 not reachable on localhost.\n"
                "Check: systemctl status research-ai-neo4j"
            )

    def test_ollama_internal(self):
        """Ollama should be accessible on localhost:11434."""
        try:
            with socket.create_connection(("127.0.0.1", 11434), timeout=3):
                pass
        except (ConnectionRefusedError, TimeoutError, OSError):
            pytest.fail(
                "Ollama port 11434 not reachable on localhost.\n"
                "Check: systemctl status research-ai-ai"
            )


# ── HTTP Endpoints ────────────────────────────────────────────────────────────

class TestProdHTTPEndpoints:
    """Test that the public-facing endpoints work end-to-end."""

    def test_frontend_serves_html(self):
        """The root URL should serve the frontend SPA."""
        try:
            resp = httpx.get(PROD_BASE_HTTPS, timeout=TIMEOUT, verify=VERIFY_SSL, follow_redirects=True)
            assert resp.status_code == 200, (
                f"Frontend returned {resp.status_code}.\n"
                "Check: podman logs research-ai-frontend"
            )
            assert "text/html" in resp.headers.get("content-type", "")
        except httpx.ConnectError as e:
            pytest.fail(f"Could not connect to {PROD_BASE_HTTPS}: {e}")

    def test_http_redirects_to_https(self):
        """HTTP should redirect to HTTPS."""
        try:
            resp = httpx.get(PROD_BASE_HTTP, timeout=TIMEOUT, follow_redirects=False)
            assert resp.status_code in (301, 302, 308), (
                f"HTTP did not redirect, got {resp.status_code}.\n"
                "Caddy should auto-redirect HTTP to HTTPS."
            )
        except httpx.ConnectError:
            pytest.skip("HTTP port not reachable")

    def test_api_health(self):
        """The API health endpoint should return ok."""
        try:
            resp = httpx.get(
                f"{PROD_BASE_HTTPS}/api/health",
                timeout=TIMEOUT,
                verify=VERIFY_SSL,
            )
            assert resp.status_code == 200
            data = resp.json()
            assert data["status"] == "ok", f"Health check returned: {data}"
            assert data["service"] == "Research-AI API"
        except httpx.ConnectError as e:
            pytest.fail(f"Could not reach API health: {e}")

    def test_api_autocomplete(self):
        """Autocomplete endpoint should respond (200 or 503 if Neo4j is starting)."""
        try:
            resp = httpx.get(
                f"{PROD_BASE_HTTPS}/api/autocomplete",
                params={"query": "utrecht", "limit": 5},
                timeout=TIMEOUT,
                verify=VERIFY_SSL,
            )
            assert resp.status_code in (200, 503), (
                f"Autocomplete returned {resp.status_code}: {resp.text}"
            )
            if resp.status_code == 200:
                data = resp.json()
                assert "persons" in data
                assert "organizations" in data
        except httpx.ConnectError as e:
            pytest.fail(f"Could not reach autocomplete: {e}")

    def test_api_connections_entity(self):
        """Connections endpoint should return mock data."""
        try:
            resp = httpx.get(
                f"{PROD_BASE_HTTPS}/api/connections/entity",
                params={"entity_id": "test-1", "entity_type": "person"},
                timeout=TIMEOUT,
                verify=VERIFY_SSL,
            )
            assert resp.status_code == 200
            data = resp.json()
            assert data["entity_type"] == "person"
            assert "collaborators" in data
            assert "publications" in data
        except httpx.ConnectError as e:
            pytest.fail(f"Could not reach connections: {e}")


# ── Inter-Container Communication ─────────────────────────────────────────────

class TestProdContainerCommunication:
    """Verify containers can talk to each other over the podman network."""

    def test_api_can_reach_neo4j(self):
        """Run a connectivity check inside the API container."""
        result = _run([
            "podman", "exec", "research-ai-api",
            "python", "-c",
            "from neo4j import GraphDatabase; import os; "
            "d = GraphDatabase.driver(os.environ['REMOTE_NEO4J_URL'], "
            "auth=(os.environ['REMOTE_NEO4J_USER'], os.environ['REMOTE_NEO4J_PASS'])); "
            "d.verify_connectivity(); d.close(); print('OK')",
        ])
        assert result.returncode == 0 and "OK" in result.stdout, (
            f"API container cannot reach Neo4j.\n"
            f"stdout: {result.stdout}\n"
            f"stderr: {result.stderr}\n"
            "Check: podman network inspect research-ai-net"
        )

    def test_api_can_reach_ollama(self):
        """Verify API container can reach the Ollama service."""
        result = _run([
            "podman", "exec", "research-ai-api",
            "python", "-c",
            "import httpx, os; "
            "r = httpx.get(os.environ['AI_SERVICE_URL'] + '/api/tags', timeout=10); "
            "print('OK' if r.status_code == 200 else f'FAIL: {r.status_code}')",
        ])
        assert result.returncode == 0 and "OK" in result.stdout, (
            f"API container cannot reach Ollama.\n"
            f"stdout: {result.stdout}\n"
            f"stderr: {result.stderr}"
        )


# ── Neo4j Database Health ─────────────────────────────────────────────────────

class TestProdNeo4jHealth:
    """Verify Neo4j is healthy and has expected indexes."""

    def test_neo4j_has_fulltext_index(self):
        """The fulltext index should exist after startup."""
        result = _run([
            "podman", "exec", "research-ai-api",
            "python", "-c",
            "from neo4j import GraphDatabase; import os; "
            "d = GraphDatabase.driver(os.environ['REMOTE_NEO4J_URL'], "
            "auth=(os.environ['REMOTE_NEO4J_USER'], os.environ['REMOTE_NEO4J_PASS'])); "
            "s = d.session(); "
            "r = s.run('SHOW FULLTEXT INDEXES YIELD name RETURN name'); "
            "names = [rec['name'] for rec in r]; "
            "s.close(); d.close(); "
            "print('FOUND' if 'ValueFulltextIndex' in names else f'MISSING from {names}')",
        ])
        assert "FOUND" in result.stdout, (
            f"Fulltext index 'ValueFulltextIndex' not found.\n"
            f"Output: {result.stdout}\n{result.stderr}\n"
            "The API startup should create this index automatically."
        )

    def test_neo4j_has_data(self):
        """Neo4j should contain at least some RicgraphNode data."""
        result = _run([
            "podman", "exec", "research-ai-api",
            "python", "-c",
            "from neo4j import GraphDatabase; import os; "
            "d = GraphDatabase.driver(os.environ['REMOTE_NEO4J_URL'], "
            "auth=(os.environ['REMOTE_NEO4J_USER'], os.environ['REMOTE_NEO4J_PASS'])); "
            "s = d.session(); "
            "r = s.run('MATCH (n:RicgraphNode) RETURN count(n) AS c'); "
            "c = r.single()['c']; s.close(); d.close(); "
            "print(f'COUNT={c}')",
        ])
        assert result.returncode == 0, f"Query failed: {result.stderr}"
        # Extract count
        for line in result.stdout.splitlines():
            if line.startswith("COUNT="):
                count = int(line.split("=")[1])
                assert count > 0, (
                    "Neo4j has 0 RicgraphNode entries.\n"
                    "Has the Ricgraph harvest been run? Try: make harvest"
                )
                break
        else:
            pytest.fail(f"Unexpected output: {result.stdout}")
