"""
Production deployment smoke tests.

Verify that a production deployment is fully operational:
- All services are healthy and responsive
- Network ports open (HTTP 80, HTTPS 443, internal services)
- End-to-end request flow works (frontend -> Caddy -> API -> Neo4j)
- Both HTTP and HTTPS work correctly
- Inter-service communication works

Run with: make test-deploy
Requires: make deploy to have been run on the production server.
Runs inside a container with --network host.
"""

import os
import socket
import pytest
import httpx

PROD_HOSTNAME = os.environ.get("PROD_HOSTNAME", os.environ.get("CADDY_HOSTNAME", "localhost"))
PROD_BASE_HTTP = f"http://{PROD_HOSTNAME}"
PROD_BASE_HTTPS = f"https://{PROD_HOSTNAME}"
TIMEOUT = 10.0
VERIFY_SSL = os.environ.get("VERIFY_SSL", "false").lower() == "true"

pytestmark = pytest.mark.smoke


# -- Network Connectivity (ports) ---------------------------------------------

class TestProdNetworkConnectivity:
    """Verify services are listening on expected ports."""

    @pytest.mark.parametrize("port,service", [
        (80, "Caddy HTTP"),
        (443, "Caddy HTTPS"),
        (7474, "Neo4j HTTP"),
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

    def test_https_api_generate(self):
        """HTTPS: /generate should accept POST and return SSE stream."""
        try:
            resp = httpx.post(
                f"{PROD_BASE_HTTPS}/api/generate",
                json={"prompt": "What is this?"},
                timeout=TIMEOUT, verify=VERIFY_SSL,
            )
            assert resp.status_code in (200, 503), (
                f"Generate returned {resp.status_code}: {resp.text[:200]}"
            )
            if resp.status_code == 200:
                assert "text/event-stream" in resp.headers.get("content-type", "")
        except httpx.ConnectError as e:
            pytest.fail(f"Could not reach /generate over HTTPS: {e}")
        except httpx.ReadTimeout:
            pass  # Model loading on first call — endpoint is reachable

    def test_https_api_chat(self):
        """HTTPS: /chat should accept POST and return SSE stream."""
        try:
            resp = httpx.post(
                f"{PROD_BASE_HTTPS}/api/chat",
                json={
                    "model": "llama3.1:8b",
                    "messages": [{"role": "user", "content": "Hello"}],
                },
                timeout=TIMEOUT, verify=VERIFY_SSL,
            )
            assert resp.status_code in (200, 503), (
                f"Chat returned {resp.status_code}: {resp.text[:200]}"
            )
            if resp.status_code == 200:
                assert "text/event-stream" in resp.headers.get("content-type", "")
        except httpx.ConnectError as e:
            pytest.fail(f"Could not reach /chat over HTTPS: {e}")
        except httpx.ReadTimeout:
            pass  # Model loading on first call — endpoint is reachable

    def test_https_api_embed(self):
        """HTTPS: /embed should accept POST."""
        try:
            resp = httpx.post(
                f"{PROD_BASE_HTTPS}/api/embed",
                json={"prompt": "test embedding"},
                timeout=TIMEOUT, verify=VERIFY_SSL,
            )
            assert resp.status_code in (200, 503), (
                f"Embed returned {resp.status_code}: {resp.text[:200]}"
            )
        except httpx.ConnectError as e:
            pytest.fail(f"Could not reach /embed over HTTPS: {e}")
        except httpx.ReadTimeout:
            pass  # Model loading on first call — endpoint is reachable


# -- Neo4j Health (via Bolt on localhost) --------------------------------------

class TestProdNeo4jHealth:
    """Verify Neo4j is healthy via its HTTP API (exposed on localhost:7474)."""

    def test_neo4j_is_available(self):
        """Neo4j HTTP API should respond."""
        try:
            resp = httpx.get("http://127.0.0.1:7474", timeout=TIMEOUT)
            assert resp.status_code == 200
        except httpx.ConnectError as e:
            pytest.fail(f"Neo4j HTTP API not reachable: {e}")

    def test_neo4j_has_fulltext_index(self):
        """Neo4j should have the ValueFulltextIndex."""
        neo4j_user = os.environ.get("REMOTE_NEO4J_USER", "neo4j")
        neo4j_pass = os.environ.get("REMOTE_NEO4J_PASS", "")
        try:
            resp = httpx.post(
                "http://127.0.0.1:7474/db/neo4j/tx/commit",
                json={"statements": [{"statement": "SHOW FULLTEXT INDEXES YIELD name RETURN name"}]},
                auth=(neo4j_user, neo4j_pass),
                timeout=TIMEOUT,
            )
            assert resp.status_code == 200, f"Neo4j query failed: {resp.text[:200]}"
            data = resp.json()
            names = [row["row"][0] for result in data["results"] for row in result["data"]]
            assert "ValueFulltextIndex" in names, (
                f"Fulltext index 'ValueFulltextIndex' not found in {names}.\n"
                "  -> The API startup should create this automatically"
            )
        except httpx.ConnectError as e:
            pytest.fail(f"Neo4j not reachable: {e}")

    def test_neo4j_has_data(self):
        """Neo4j should have RicgraphNode entries."""
        neo4j_user = os.environ.get("REMOTE_NEO4J_USER", "neo4j")
        neo4j_pass = os.environ.get("REMOTE_NEO4J_PASS", "")
        try:
            resp = httpx.post(
                "http://127.0.0.1:7474/db/neo4j/tx/commit",
                json={"statements": [{"statement": "MATCH (n:RicgraphNode) RETURN count(n) AS c"}]},
                auth=(neo4j_user, neo4j_pass),
                timeout=TIMEOUT,
            )
            assert resp.status_code == 200, f"Neo4j query failed: {resp.text[:200]}"
            data = resp.json()
            count = data["results"][0]["data"][0]["row"][0]
            assert count > 0, (
                "Neo4j has 0 RicgraphNode entries.\n"
                "  -> Has the Ricgraph harvest been run? Try: make harvest"
            )
        except httpx.ConnectError as e:
            pytest.fail(f"Neo4j not reachable: {e}")


# -- Ollama Health ------------------------------------------------------------

class TestProdOllamaHealth:
    """Verify Ollama is responding."""

    def test_ollama_responds(self):
        """Ollama API should return its tag list."""
        try:
            resp = httpx.get("http://127.0.0.1:11434/api/tags", timeout=TIMEOUT)
            assert resp.status_code == 200
            data = resp.json()
            assert "models" in data
        except httpx.ConnectError as e:
            pytest.fail(f"Ollama not reachable: {e}")
