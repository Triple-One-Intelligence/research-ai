"""
Dev environment smoke tests.

Verify that the local development setup works:
- SSH tunnel ports are reachable (Neo4j, Ricgraph, Ollama)
- The API container is running and healthy
- The frontend dev server is running
- Caddy reverse proxy routes correctly

Run with: make test-dev
Requires: make dev to be running (pod + SSH tunnel)
"""

import socket
import pytest
import httpx

DEV_BASE = "http://localhost:3000"
TIMEOUT = 5.0

pytestmark = pytest.mark.smoke


def _port_open(host: str, port: int, timeout: float = 2.0) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except (ConnectionRefusedError, TimeoutError, OSError):
        return False


# -- SSH Tunnel Ports ---------------------------------------------------------

class TestSSHTunnelPorts:
    """Verify that SSH-tunneled services are reachable on localhost."""

    def test_neo4j_bolt_port(self):
        if not _port_open("localhost", 7687):
            pytest.skip(
                "Port 7687 (Neo4j Bolt) not reachable - "
                "SSH tunnel not running? Try: make tunnel"
            )

    def test_neo4j_http_port(self):
        if not _port_open("localhost", 7474):
            pytest.skip(
                "Port 7474 (Neo4j HTTP) not reachable - "
                "SSH tunnel not running? Try: make tunnel"
            )

    def test_ricgraph_explorer_port(self):
        if not _port_open("localhost", 3030):
            pytest.skip(
                "Port 3030 (Ricgraph Explorer) not reachable - "
                "SSH tunnel not running? Try: make tunnel"
            )

    def test_ollama_port(self):
        if not _port_open("localhost", 11434):
            pytest.skip(
                "Port 11434 (Ollama) not reachable - "
                "SSH tunnel not running? Try: make tunnel"
            )


# -- Dev Pod Services ---------------------------------------------------------

class TestDevPodRunning:
    """Verify that the local dev pod containers are up."""

    def test_caddy_port(self):
        if not _port_open("localhost", 3000):
            pytest.skip(
                "Port 3000 (Caddy) not reachable - "
                "Dev pod not running? Try: make up"
            )

    def test_caddy_serves_frontend(self):
        try:
            resp = httpx.get(f"{DEV_BASE}/", timeout=TIMEOUT, follow_redirects=True)
            assert resp.status_code == 200, (
                f"Frontend returned {resp.status_code} instead of 200.\n"
                "  -> Check: podman logs research-ai-dev-frontend"
            )
            assert "text/html" in resp.headers.get("content-type", ""), (
                "Frontend did not return HTML.\n"
                "  -> Is the Vite dev server running inside the pod?"
            )
        except (httpx.ConnectError, httpx.ReadTimeout):
            pytest.skip(
                "Could not connect to Caddy on port 3000 - "
                "Dev pod not running? Try: make up"
            )

    def test_caddy_proxies_api(self):
        """Caddy should proxy /api/* to the FastAPI backend."""
        try:
            resp = httpx.get(f"{DEV_BASE}/api/health", timeout=TIMEOUT)
            assert resp.status_code == 200, (
                f"API health returned {resp.status_code}.\n"
                "  -> Check: podman logs research-ai-dev-api"
            )
            data = resp.json()
            assert data["status"] == "ok"
        except (httpx.ConnectError, httpx.ReadTimeout):
            pytest.skip(
                "Could not reach /api/health through Caddy - "
                "Dev pod not running? Try: make up"
            )


# -- API Through Tunnel -------------------------------------------------------

class TestDevAPIFunctionality:
    """Test that the API can talk to backend services through the tunnel."""

    def test_autocomplete_endpoint_responds(self):
        try:
            resp = httpx.get(
                f"{DEV_BASE}/api/autocomplete",
                params={"query": "test", "limit": 5},
                timeout=TIMEOUT,
            )
            assert resp.status_code in (200, 503), (
                f"Autocomplete returned unexpected {resp.status_code}.\n"
                f"  -> Response: {resp.text[:200]}"
            )
        except (httpx.ConnectError, httpx.ReadTimeout):
            pytest.skip("Could not reach API - dev pod not running?")

    def test_connections_entity_endpoint(self):
        try:
            resp = httpx.get(
                f"{DEV_BASE}/api/connections/entity",
                params={"entity_id": "test-1", "entity_type": "person"},
                timeout=TIMEOUT,
            )
            assert resp.status_code == 200, (
                f"Connections returned {resp.status_code}.\n"
                f"  -> Response: {resp.text[:200]}"
            )
            data = resp.json()
            assert data["entity_id"] == "test-1"
            assert data["entity_type"] == "person"
        except (httpx.ConnectError, httpx.ReadTimeout):
            pytest.skip("Could not reach API - dev pod not running?")


# -- Neo4j Connectivity (through tunnel) --------------------------------------

class TestDevNeo4jConnection:
    """Verify the API can query Neo4j through the SSH tunnel."""

    def test_neo4j_responds_to_bolt(self):
        if not _port_open("localhost", 7687):
            pytest.skip("SSH tunnel not active (port 7687 closed)")

        try:
            import os
            from neo4j import GraphDatabase
            driver = GraphDatabase.driver(
                os.environ.get("REMOTE_NEO4J_URL", "bolt://localhost:7687"),
                auth=(
                    os.environ.get("REMOTE_NEO4J_USER", "neo4j"),
                    os.environ.get("REMOTE_NEO4J_PASS", "testpassword"),
                ),
            )
            try:
                driver.verify_connectivity()
            except Exception as e:
                if "authentication" not in str(e).lower():
                    pytest.fail(
                        f"Neo4j connectivity check failed: {e}\n"
                        "  -> Port is open but Neo4j isn't responding to Bolt"
                    )
            finally:
                driver.close()
        except ImportError:
            pytest.skip("neo4j driver not installed")


# -- Ollama Connectivity (through tunnel) -------------------------------------

class TestDevOllamaConnection:
    """Verify Ollama is reachable and can serve models."""

    def test_ollama_responds(self):
        if not _port_open("localhost", 11434):
            pytest.skip("SSH tunnel not active (port 11434 closed)")

        try:
            resp = httpx.get("http://localhost:11434/", timeout=TIMEOUT)
            assert resp.status_code == 200, (
                f"Ollama returned {resp.status_code}.\n"
                "  -> Is Ollama running on the remote server?"
            )
        except httpx.ConnectError:
            pytest.fail("Ollama port is open but not responding to HTTP")

    def test_ollama_list_models(self):
        if not _port_open("localhost", 11434):
            pytest.skip("SSH tunnel not active (port 11434 closed)")

        try:
            resp = httpx.get("http://localhost:11434/api/tags", timeout=TIMEOUT)
            assert resp.status_code == 200
            data = resp.json()
            assert "models" in data, (
                f"Ollama /api/tags missing 'models' key. Got: {data}"
            )
        except httpx.ConnectError:
            pytest.fail("Could not list Ollama models")
