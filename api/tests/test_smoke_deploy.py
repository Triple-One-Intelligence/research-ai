"""
Production deployment smoke tests.

Verify that a production deployment is fully operational:
- All systemd services are running
- All containers are healthy and responsive
- Network ports open (HTTP 80, HTTPS 443, internal services)
- End-to-end request flow works (frontend -> Caddy -> API -> Neo4j)
- Both HTTP and HTTPS work correctly

Run with: make test-deploy
Requires: make deploy to have been run on the production server.
Must be run ON the production server itself.
"""

import os
import subprocess
import socket
import pytest
import httpx

PROD_HOSTNAME = os.environ.get("PROD_HOSTNAME", os.environ.get("CADDY_HOSTNAME", "localhost"))
PROD_BASE_HTTP = f"http://{PROD_HOSTNAME}"
PROD_BASE_HTTPS = f"https://{PROD_HOSTNAME}"
TIMEOUT = 10.0
VERIFY_SSL = os.environ.get("VERIFY_SSL", "false").lower() == "true"

pytestmark = pytest.mark.smoke

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


# -- Systemd Services ---------------------------------------------------------

class TestSystemdServices:
    """Verify all systemd units are active."""

    @pytest.mark.parametrize("service", SYSTEMD_SERVICES)
    def test_service_is_active(self, service):
        result = _run(["systemctl", "is-active", service])
        status = result.stdout.strip()
        if status != "active":
            log_result = _run(["journalctl", "-u", service, "-n", "20", "--no-pager"])
            pytest.fail(
                f"Service {service} is '{status}', expected 'active'.\n"
                f"  -> Recent logs:\n{log_result.stdout}"
            )


# -- Podman Containers --------------------------------------------------------

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
                f"  -> Recent logs:\n{log_result.stdout}\n{log_result.stderr}"
            )

    def test_podman_network_exists(self):
        result = _run(["podman", "network", "inspect", "research-ai-net"])
        assert result.returncode == 0, (
            "Podman network 'research-ai-net' does not exist.\n"
            "  -> Run: make deploy"
        )


# -- Network Connectivity (ports) ---------------------------------------------

class TestProdNetworkConnectivity:
    """Verify services are listening on expected ports."""

    @pytest.mark.parametrize("port,service", [
        (80, "Caddy HTTP"),
        (443, "Caddy HTTPS"),
        (7687, "Neo4j Bolt"),
        (11434, "Ollama"),
    ])
    def test_port_open(self, port, service):
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=3):
                pass
        except (ConnectionRefusedError, TimeoutError, OSError):
            pytest.fail(
                f"Port {port} ({service}) is not open.\n"
                f"  -> Check the relevant service is running"
            )


# -- HTTP Endpoints -----------------------------------------------------------

class TestProdHTTPEndpoints:
    """Test public-facing endpoints work end-to-end over both HTTP and HTTPS."""

    def test_https_frontend_serves_html(self):
        """HTTPS: root URL should serve the frontend SPA."""
        try:
            resp = httpx.get(PROD_BASE_HTTPS, timeout=TIMEOUT, verify=VERIFY_SSL, follow_redirects=True)
            assert resp.status_code == 200, (
                f"Frontend returned {resp.status_code} over HTTPS.\n"
                "  -> Check: podman logs research-ai-frontend"
            )
            assert "text/html" in resp.headers.get("content-type", "")
        except httpx.ConnectError as e:
            pytest.fail(f"Could not connect to {PROD_BASE_HTTPS}: {e}")

    def test_http_redirects_to_https(self):
        """HTTP on port 80 should redirect to HTTPS on port 443."""
        try:
            resp = httpx.get(PROD_BASE_HTTP, timeout=TIMEOUT, follow_redirects=False)
            assert resp.status_code in (301, 302, 308), (
                f"HTTP did not redirect to HTTPS, got {resp.status_code}.\n"
                "  -> Caddy should auto-redirect HTTP -> HTTPS"
            )
            location = resp.headers.get("location", "")
            assert "https://" in location, (
                f"Redirect location doesn't point to HTTPS: {location}"
            )
        except httpx.ConnectError:
            pytest.skip("HTTP port 80 not reachable")

    def test_https_api_health(self):
        """HTTPS: API health endpoint should return ok."""
        try:
            resp = httpx.get(
                f"{PROD_BASE_HTTPS}/api/health",
                timeout=TIMEOUT, verify=VERIFY_SSL,
            )
            assert resp.status_code == 200
            data = resp.json()
            assert data["status"] == "ok", f"Health: {data}"
            assert data["service"] == "Research-AI API"
        except httpx.ConnectError as e:
            pytest.fail(f"Could not reach API health over HTTPS: {e}")

    def test_https_api_autocomplete(self):
        """HTTPS: autocomplete should respond (200 or 503 if Neo4j starting)."""
        try:
            resp = httpx.get(
                f"{PROD_BASE_HTTPS}/api/autocomplete",
                params={"query": "utrecht", "limit": 5},
                timeout=TIMEOUT, verify=VERIFY_SSL,
            )
            assert resp.status_code in (200, 503), (
                f"Autocomplete returned {resp.status_code}: {resp.text[:200]}"
            )
            if resp.status_code == 200:
                data = resp.json()
                assert "persons" in data
                assert "organizations" in data
        except httpx.ConnectError as e:
            pytest.fail(f"Could not reach autocomplete over HTTPS: {e}")

    def test_https_api_connections(self):
        """HTTPS: connections endpoint should return data."""
        try:
            resp = httpx.get(
                f"{PROD_BASE_HTTPS}/api/connections/entity",
                params={"entity_id": "test-1", "entity_type": "person"},
                timeout=TIMEOUT, verify=VERIFY_SSL,
            )
            assert resp.status_code == 200
            data = resp.json()
            assert data["entity_type"] == "person"
            assert "collaborators" in data
            assert "publications" in data
        except httpx.ConnectError as e:
            pytest.fail(f"Could not reach connections over HTTPS: {e}")


# -- Inter-Container Communication --------------------------------------------

class TestProdContainerCommunication:
    """Verify containers can talk to each other over the podman network."""

    def test_api_can_reach_neo4j(self):
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
            f"  -> stdout: {result.stdout}\n"
            f"  -> stderr: {result.stderr}\n"
            "  -> Check: podman network inspect research-ai-net"
        )

    def test_api_can_reach_ollama(self):
        result = _run([
            "podman", "exec", "research-ai-api",
            "python", "-c",
            "import httpx, os; "
            "r = httpx.get(os.environ['AI_SERVICE_URL'] + '/api/tags', timeout=10); "
            "print('OK' if r.status_code == 200 else f'FAIL: {r.status_code}')",
        ])
        assert result.returncode == 0 and "OK" in result.stdout, (
            f"API container cannot reach Ollama.\n"
            f"  -> stdout: {result.stdout}\n"
            f"  -> stderr: {result.stderr}"
        )


# -- Neo4j Database Health ----------------------------------------------------

class TestProdNeo4jHealth:
    """Verify Neo4j is healthy and has expected indexes."""

    def test_neo4j_has_fulltext_index(self):
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
            f"  -> Output: {result.stdout}\n{result.stderr}\n"
            "  -> The API startup should create this automatically"
        )

    def test_neo4j_has_data(self):
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
        for line in result.stdout.splitlines():
            if line.startswith("COUNT="):
                count = int(line.split("=")[1])
                assert count > 0, (
                    "Neo4j has 0 RicgraphNode entries.\n"
                    "  -> Has the Ricgraph harvest been run? Try: make harvest"
                )
                break
        else:
            pytest.fail(f"Unexpected output: {result.stdout}")
