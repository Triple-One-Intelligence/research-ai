"""
Dev environment smoke tests.

These tests verify that the local development setup works:
- SSH tunnel ports are reachable (Neo4j, Ricgraph, Ollama)
- The API container is running and healthy
- The frontend dev server is running
- Caddy reverse proxy routes correctly

Run with: make test-dev
Requires: `make dev` to be running (pod + SSH tunnel)
"""

import socket
import pytest
import httpx

DEV_BASE = "http://localhost:8080"
TIMEOUT = 5.0


def _port_open(host: str, port: int, timeout: float = 2.0) -> bool:
    """Check if a TCP port is accepting connections."""
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except (ConnectionRefusedError, TimeoutError, OSError):
        return False


# ── SSH Tunnel Ports ──────────────────────────────────────────────────────────

class TestSSHTunnelPorts:
    """Verify that SSH-tunneled services are reachable on localhost."""

    def test_neo4j_bolt_port(self):
        """Neo4j Bolt protocol should be forwarded on port 7687."""
        assert _port_open("localhost", 7687), (
            "Port 7687 (Neo4j Bolt) is not reachable.\n"
            "Is the SSH tunnel running? Try: make tunnel\n"
            "Check that Neo4j is running on the remote server."
        )

    def test_neo4j_http_port(self):
        """Neo4j HTTP browser should be forwarded on port 7474."""
        assert _port_open("localhost", 7474), (
            "Port 7474 (Neo4j HTTP) is not reachable.\n"
            "Is the SSH tunnel running? Try: make tunnel"
        )

    def test_ricgraph_explorer_port(self):
        """Ricgraph Explorer should be forwarded on port 3030."""
        assert _port_open("localhost", 3030), (
            "Port 3030 (Ricgraph Explorer) is not reachable.\n"
            "Is the SSH tunnel running? Try: make tunnel\n"
            "Check: ssh root@0xai.nl 'systemctl status research-ai-ricgraph'"
        )

    def test_ollama_port(self):
        """Ollama AI service should be forwarded on port 11434."""
        assert _port_open("localhost", 11434), (
            "Port 11434 (Ollama) is not reachable.\n"
            "Is the SSH tunnel running? Try: make tunnel\n"
            "Check: ssh root@0xai.nl 'systemctl status research-ai-ai'"
        )


# ── Dev Pod Services ──────────────────────────────────────────────────────────

class TestDevPodRunning:
    """Verify that the local dev pod containers are up."""

    def test_caddy_port(self):
        """Caddy reverse proxy should be on port 8080."""
        assert _port_open("localhost", 8080), (
            "Port 8080 (Caddy) is not reachable.\n"
            "Is the dev pod running? Try: make up"
        )

    def test_caddy_serves_frontend(self):
        """Caddy should proxy the root path to the frontend."""
        try:
            resp = httpx.get(f"{DEV_BASE}/", timeout=TIMEOUT, follow_redirects=True)
            assert resp.status_code == 200, (
                f"Frontend returned {resp.status_code} instead of 200.\n"
                "Check: podman logs research-ai-dev-frontend"
            )
            assert "text/html" in resp.headers.get("content-type", ""), (
                "Frontend did not return HTML.\n"
                "Is the Vite dev server running inside the pod?"
            )
        except httpx.ConnectError:
            pytest.fail(
                "Could not connect to Caddy on port 8080.\n"
                "Is the dev pod running? Try: make up"
            )

    def test_caddy_proxies_api(self):
        """Caddy should proxy /api/* to the FastAPI backend."""
        try:
            resp = httpx.get(f"{DEV_BASE}/api/health", timeout=TIMEOUT)
            assert resp.status_code == 200, (
                f"API health returned {resp.status_code}.\n"
                "Check: podman logs research-ai-dev-api"
            )
            data = resp.json()
            assert data["status"] == "ok"
        except httpx.ConnectError:
            pytest.fail(
                "Could not reach /api/health through Caddy.\n"
                "Check that both Caddy and the API container are running."
            )


# ── API Through Tunnel ────────────────────────────────────────────────────────

class TestDevAPIFunctionality:
    """Test that the API can actually talk to backend services through the tunnel."""

    def test_autocomplete_endpoint_responds(self):
        """The autocomplete endpoint should respond (even if Neo4j returns nothing)."""
        try:
            resp = httpx.get(
                f"{DEV_BASE}/api/autocomplete",
                params={"query": "test", "limit": 5},
                timeout=TIMEOUT,
            )
            # 200 = working, 503 = Neo4j not reachable but API itself is fine
            assert resp.status_code in (200, 503), (
                f"Autocomplete returned unexpected status {resp.status_code}.\n"
                f"Response: {resp.text}"
            )
        except httpx.ConnectError:
            pytest.fail("Could not reach API. Is the dev pod running?")

    def test_connections_entity_endpoint(self):
        """The connections endpoint should return mock data."""
        try:
            resp = httpx.get(
                f"{DEV_BASE}/api/connections/entity",
                params={"entity_id": "test-1", "entity_type": "person"},
                timeout=TIMEOUT,
            )
            assert resp.status_code == 200, (
                f"Connections endpoint returned {resp.status_code}.\n"
                f"Response: {resp.text}"
            )
            data = resp.json()
            assert data["entity_id"] == "test-1"
            assert data["entity_type"] == "person"
        except httpx.ConnectError:
            pytest.fail("Could not reach API. Is the dev pod running?")


# ── Neo4j Connectivity (through tunnel) ──────────────────────────────────────

class TestDevNeo4jConnection:
    """Verify the API can actually query Neo4j through the SSH tunnel."""

    def test_neo4j_responds_to_bolt(self):
        """Neo4j should accept Bolt connections on the tunneled port."""
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
                # Auth may fail but connectivity should work
                if "authentication" not in str(e).lower():
                    pytest.fail(
                        f"Neo4j connectivity check failed: {e}\n"
                        "The port is open but Neo4j isn't responding to Bolt."
                    )
            finally:
                driver.close()
        except ImportError:
            pytest.skip("neo4j driver not installed")


# ── Ollama Connectivity (through tunnel) ──────────────────────────────────────

class TestDevOllamaConnection:
    """Verify Ollama is reachable and can serve models."""

    def test_ollama_responds(self):
        """Ollama root endpoint should return a response."""
        if not _port_open("localhost", 11434):
            pytest.skip("SSH tunnel not active (port 11434 closed)")

        try:
            resp = httpx.get("http://localhost:11434/", timeout=TIMEOUT)
            assert resp.status_code == 200, (
                f"Ollama returned {resp.status_code}.\n"
                "Is the Ollama service running on the remote server?"
            )
        except httpx.ConnectError:
            pytest.fail("Ollama port is open but not responding to HTTP.")

    def test_ollama_list_models(self):
        """Ollama should be able to list available models."""
        if not _port_open("localhost", 11434):
            pytest.skip("SSH tunnel not active (port 11434 closed)")

        try:
            resp = httpx.get("http://localhost:11434/api/tags", timeout=TIMEOUT)
            assert resp.status_code == 200
            data = resp.json()
            assert "models" in data, (
                "Ollama /api/tags response missing 'models' key.\n"
                f"Got: {data}"
            )
        except httpx.ConnectError:
            pytest.fail("Could not list Ollama models.")
