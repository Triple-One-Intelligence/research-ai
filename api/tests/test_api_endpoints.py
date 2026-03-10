"""Tests for FastAPI endpoints (autocomplete, health, AI proxy)."""

import os
from unittest.mock import patch, MagicMock, AsyncMock
import pytest
from fastapi.testclient import TestClient

CHAT_MODEL = os.getenv("CHAT_MODEL", "tinyllama")


@pytest.fixture
def client():
    """Create a test client with mocked database startup."""
    with patch("app.utils.database_utils.database_utils.startup"):
        with patch("app.utils.database_utils.database_utils.shutdown"):
            from app.main import app
            with TestClient(app) as c:
                yield c


class TestHealthEndpoint:
    def test_health_returns_ok(self, client):
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert data["service"] == "Research-AI API"
        assert "time" in data


class TestAutocompleteEndpoint:
    @patch("app.routers.autocomplete.get_autocomplete_suggestions")
    def test_autocomplete_success(self, mock_ac, client):
        from app.utils.schemas import Suggestions, Person

        mock_ac.return_value = Suggestions(
            persons=[Person(author_id="p1", name="John Doe")],
            organizations=[],
        )

        response = client.get("/autocomplete", params={"query": "john"})
        assert response.status_code == 200
        data = response.json()
        assert len(data["persons"]) == 1
        assert data["persons"][0]["name"] == "John Doe"

    @patch("app.routers.autocomplete.get_autocomplete_suggestions")
    def test_autocomplete_with_limit(self, mock_ac, client):
        from app.utils.schemas import Suggestions

        mock_ac.return_value = Suggestions(persons=[], organizations=[])

        response = client.get("/autocomplete", params={"query": "test", "limit": 5})
        assert response.status_code == 200
        mock_ac.assert_called_once_with("test", 5)

    def test_autocomplete_missing_query(self, client):
        response = client.get("/autocomplete")
        assert response.status_code == 422  # validation error

    def test_autocomplete_limit_too_high(self, client):
        response = client.get("/autocomplete", params={"query": "test", "limit": 200})
        assert response.status_code == 422

    def test_autocomplete_limit_too_low(self, client):
        response = client.get("/autocomplete", params={"query": "test", "limit": 0})
        assert response.status_code == 422

    @patch("app.routers.autocomplete.get_autocomplete_suggestions")
    def test_autocomplete_db_error_returns_503(self, mock_ac, client):
        from neo4j.exceptions import ServiceUnavailable

        mock_ac.side_effect = ServiceUnavailable("db down")

        response = client.get("/autocomplete", params={"query": "test"})
        assert response.status_code == 503

    @patch("app.routers.autocomplete.get_autocomplete_suggestions")
    def test_autocomplete_runtime_error_returns_503(self, mock_ac, client):
        mock_ac.side_effect = RuntimeError("not initialized")

        response = client.get("/autocomplete", params={"query": "test"})
        assert response.status_code == 503


class TestChatEndpoint:
    @patch("app.ai.httpx.AsyncClient")
    def test_chat_success(self, mock_client_cls, client):
        mock_response = MagicMock()
        mock_response.json.return_value = {"message": {"content": "hello"}}
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.post.return_value = mock_response
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client_cls.return_value = mock_client

        response = client.post("/chat", json={
            "model": CHAT_MODEL,
            "messages": [{"role": "user", "content": "hi"}],
        })
        assert response.status_code == 200

    @patch("app.ai.httpx.AsyncClient")
    def test_chat_service_unavailable(self, mock_client_cls, client):
        import httpx

        mock_client = AsyncMock()
        mock_client.post.side_effect = httpx.RequestError("connection refused")
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client_cls.return_value = mock_client

        response = client.post("/chat", json={
            "model": CHAT_MODEL,
            "messages": [{"role": "user", "content": "hi"}],
        })
        assert response.status_code == 503


class TestEmbedEndpoint:
    @patch("app.ai.httpx.AsyncClient")
    def test_embed_success(self, mock_client_cls, client):
        mock_response = MagicMock()
        mock_response.json.return_value = {"embedding": [0.1, 0.2]}
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.post.return_value = mock_response
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client_cls.return_value = mock_client

        response = client.post("/embed", json={
            "model": "nomic-embed-text",
            "prompt": "test text",
        })
        assert response.status_code == 200
        assert response.json()["embedding"] == [0.1, 0.2]
