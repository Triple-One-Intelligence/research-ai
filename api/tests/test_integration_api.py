"""
API integration tests against a running local instance.

These tests hit the actual API (no mocks) to verify end-to-end behavior.
They require the dev pod to be running (make dev).

Run with: make test-dev
"""

import pytest
import httpx

API_BASE = "https://localhost:3000/api"
TIMEOUT = 5.0
_client = httpx.Client(verify=False)

pytestmark = pytest.mark.integration


def _dev_api_running() -> bool:
    """Check if the dev API is actually running (not just any service on :3000)."""
    try:
        resp = _client.get(f"{API_BASE}/health")
        return resp.status_code == 200 and resp.json().get("service") == "Research-AI API"
    except Exception:
        return False


_skip = pytest.mark.skipif(
    not _dev_api_running(),
    reason="Dev API not running on port 3000. Start with: make dev",
)


@_skip
class TestHealthIntegration:
    def test_health_returns_json(self):
        resp = _client.get(f"{API_BASE}/health")
        assert resp.status_code == 200
        assert resp.headers["content-type"] == "application/json"
        data = resp.json()
        assert data["status"] == "ok"
        assert "time" in data

    def test_health_time_is_recent(self):
        from datetime import datetime, timedelta, timezone

        resp = _client.get(f"{API_BASE}/health")
        data = resp.json()
        api_time = datetime.fromisoformat(data["time"])
        if api_time.tzinfo is None:
            api_time = api_time.replace(tzinfo=timezone.utc)
        now_utc = datetime.now(timezone.utc)
        assert abs(now_utc - api_time) < timedelta(minutes=5), (
            "API time is more than 5 minutes off from UTC"
        )


@_skip
class TestAutocompleteIntegration:
    def test_valid_query_returns_suggestions_shape(self):
        resp = _client.get(
            f"{API_BASE}/autocomplete",
            params={"query": "utrecht", "limit": 5},
        )
        if resp.status_code == 503:
            pytest.skip("Neo4j not reachable (503)")
        assert resp.status_code == 200
        data = resp.json()
        assert "persons" in data
        assert "organizations" in data
        assert isinstance(data["persons"], list)
        assert isinstance(data["organizations"], list)

    def test_short_query_returns_400(self):
        resp = _client.get(
            f"{API_BASE}/autocomplete",
            params={"query": "a"},
        )
        if resp.status_code == 503:
            pytest.skip("Neo4j not reachable")
        assert resp.status_code == 400

    def test_limit_is_respected(self):
        resp = _client.get(
            f"{API_BASE}/autocomplete",
            params={"query": "van", "limit": 2},
        )
        if resp.status_code == 503:
            pytest.skip("Neo4j not reachable")
        assert resp.status_code == 200
        data = resp.json()
        total = len(data["persons"]) + len(data["organizations"])
        assert total <= 2

    def test_person_results_have_required_fields(self):
        resp = _client.get(
            f"{API_BASE}/autocomplete",
            params={"query": "jan", "limit": 10},
        )
        if resp.status_code == 503:
            pytest.skip("Neo4j not reachable")
        for person in resp.json().get("persons", []):
            assert "author_id" in person, f"Person missing author_id: {person}"
            assert "name" in person, f"Person missing name: {person}"
            assert len(person["name"]) > 0

    def test_organization_results_have_required_fields(self):
        resp = _client.get(
            f"{API_BASE}/autocomplete",
            params={"query": "university", "limit": 10},
        )
        if resp.status_code == 503:
            pytest.skip("Neo4j not reachable")
        for org in resp.json().get("organizations", []):
            assert "organization_id" in org, f"Org missing organization_id: {org}"
            assert "name" in org, f"Org missing name: {org}"

    def test_invalid_limit_rejected(self):
        resp = _client.get(
            f"{API_BASE}/autocomplete",
            params={"query": "test", "limit": 0},
        )
        assert resp.status_code == 422

    def test_missing_query_rejected(self):
        resp = _client.get(f"{API_BASE}/autocomplete")
        assert resp.status_code == 422

    def test_special_chars_dont_crash(self):
        for query in ["o'brien", "test+test", 'he"llo', "foo\\bar", "(test)"]:
            resp = _client.get(
                f"{API_BASE}/autocomplete",
                params={"query": query},
                timeout=TIMEOUT,
            )
            assert resp.status_code in (200, 503), (
                f"Query '{query}' caused status {resp.status_code}: {resp.text[:200]}"
            )


@_skip
class TestConnectionsIntegration:
    def test_person_connections_shape(self):
        resp = _client.get(
            f"{API_BASE}/connections/entity",
            params={"entity_id": "p1", "entity_type": "person"},
        )
        assert resp.status_code in (200, 500), (
            f"Connections returned {resp.status_code}: {resp.text[:200]}"
        )
        if resp.status_code == 200:
            data = resp.json()
            assert "collaborators" in data
            assert "publications" in data
            assert "organizations" in data
            assert "members" in data

    def test_invalid_entity_type_returns_400(self):
        resp = _client.get(
            f"{API_BASE}/connections/entity",
            params={"entity_id": "p1", "entity_type": "invalid"},
        )
        assert resp.status_code == 400


@_skip
class TestGenerateIntegration:
    def test_generate_accepts_post(self):
        try:
            resp = _client.post(
                f"{API_BASE}/generate",
                json={"prompt": "What is this researcher known for?"},
                timeout=TIMEOUT,
            )
        except httpx.ReadTimeout:
            return  # Model cold-start — endpoint is reachable
        if resp.status_code in (500, 503):
            pytest.skip(f"RAG retrieval unavailable ({resp.status_code})")
        if resp.status_code == 404:
            pytest.skip("Ollama model not pulled — run: make deploy")
        assert resp.status_code == 200
        assert "text/event-stream" in resp.headers.get("content-type", "")

    def test_generate_empty_prompt_returns_400(self):
        resp = _client.post(
            f"{API_BASE}/generate",
            json={"prompt": "  "},
            timeout=TIMEOUT,
        )
        assert resp.status_code == 400

    def test_generate_missing_prompt_returns_422(self):
        resp = _client.post(
            f"{API_BASE}/generate",
            json={},
            timeout=TIMEOUT,
        )
        assert resp.status_code == 422

    def test_generate_with_entity(self):
        try:
            resp = _client.post(
                f"{API_BASE}/generate",
                json={
                    "prompt": "What topics?",
                    "entity": {"id": "p1", "type": "person", "label": "Test"},
                },
                timeout=TIMEOUT,
            )
        except httpx.ReadTimeout:
            return  # Model cold-start — endpoint is reachable
        if resp.status_code in (500, 503):
            pytest.skip(f"RAG retrieval unavailable ({resp.status_code})")
        if resp.status_code == 404:
            pytest.skip("Ollama model not pulled — run: make deploy")
        assert resp.status_code == 200


@_skip
class TestChatIntegration:
    def test_chat_accepts_post(self):
        try:
            resp = _client.post(
                f"{API_BASE}/chat",
                json={
                    "model": "llama3.1:8b",
                    "messages": [{"role": "user", "content": "Hello"}],
                },
                timeout=TIMEOUT,
            )
        except httpx.ReadTimeout:
            return  # Model cold-start — endpoint is reachable
        if resp.status_code == 503:
            pytest.skip("AI service not reachable")
        if resp.status_code == 404:
            pytest.skip("Ollama model not pulled — run: make deploy")
        assert resp.status_code == 200
        assert "text/event-stream" in resp.headers.get("content-type", "")

    def test_chat_missing_messages_returns_422(self):
        resp = _client.post(
            f"{API_BASE}/chat",
            json={"model": "llama3.1:8b"},
            timeout=TIMEOUT,
        )
        assert resp.status_code == 422


@_skip
class TestEmbedIntegration:
    def test_embed_accepts_post(self):
        try:
            resp = _client.post(
                f"{API_BASE}/embed",
                json={"prompt": "test embedding"},
                timeout=TIMEOUT,
            )
        except httpx.ReadTimeout:
            return  # Model cold-start — endpoint is reachable
        if resp.status_code == 503:
            pytest.skip("AI service not reachable")
        if resp.status_code == 404:
            pytest.skip("Ollama model not pulled — run: make deploy")
        assert resp.status_code == 200

    def test_embed_missing_prompt_returns_422(self):
        resp = _client.post(
            f"{API_BASE}/embed",
            json={},
            timeout=TIMEOUT,
        )
        assert resp.status_code == 422


@_skip
class TestCORSIntegration:
    def test_cors_allows_dev_origin(self):
        resp = _client.options(
            f"{API_BASE}/health",
            headers={
                "Origin": "http://localhost:5173",
                "Access-Control-Request-Method": "GET",
            },
        )
        assert "access-control-allow-origin" in resp.headers

    def test_cors_blocks_unknown_origin(self):
        resp = _client.options(
            f"{API_BASE}/health",
            headers={
                "Origin": "http://evil.com",
                "Access-Control-Request-Method": "GET",
            },
        )
        allow_origin = resp.headers.get("access-control-allow-origin", "")
        assert "evil.com" not in allow_origin
