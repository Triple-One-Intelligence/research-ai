"""Tests for FastAPI endpoints (autocomplete, health, AI proxy)."""

import os
from unittest.mock import patch, MagicMock, AsyncMock
import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.utils.schemas.ai import EntityRef

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


class _MockStream:
    """Mock for httpx async streaming response."""
    def __init__(self, lines=None, error=None):
        self._lines = lines or []
        self._error = error

    async def __aenter__(self):
        if self._error:
            raise self._error
        return self

    async def __aexit__(self, *args):
        pass

    def raise_for_status(self):
        pass

    async def aiter_lines(self):
        for line in self._lines:
            yield line


class TestChatEndpoint:
    @patch("app.routers.ai.httpx.AsyncClient")
    def test_chat_success(self, mock_client_cls, client):
        mock_stream = _MockStream(lines=[
            '{"message":{"content":"hello"},"done":false}',
            '{"message":{"content":""},"done":true}',
        ])

        mock_client = AsyncMock()
        mock_client.stream = MagicMock(return_value=mock_stream)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client_cls.return_value = mock_client

        response = client.post("/chat", json={
            "model": CHAT_MODEL,
            "messages": [{"role": "user", "content": "hi"}],
        })
        assert response.status_code == 200
        assert "text/event-stream" in response.headers["content-type"]

    @patch("app.routers.ai.httpx.AsyncClient")
    def test_chat_service_unavailable(self, mock_client_cls, client):
        import httpx

        mock_stream = _MockStream(
            error=httpx.RequestError("connection refused")
        )

        mock_client = AsyncMock()
        mock_client.stream = MagicMock(return_value=mock_stream)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client_cls.return_value = mock_client

        response = client.post("/chat", json={
            "model": CHAT_MODEL,
            "messages": [{"role": "user", "content": "hi"}],
        })
        assert response.status_code == 200
        assert "error" in response.text


class TestEmbedEndpoint:
    @patch("app.utils.ai_utils.ai_utils.httpx.AsyncClient")
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

    @patch("app.utils.ai_utils.ai_utils.httpx.AsyncClient")
    def test_embed_uses_send_async_ai_request(self, mock_client_cls, client):
        """Verify /embed delegates to send_async_ai_request (not raw httpx)."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"embedding": [0.3]}
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.post.return_value = mock_response
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client_cls.return_value = mock_client

        response = client.post("/embed", json={"prompt": "test"})
        assert response.status_code == 200
        # Verify the post was called with the AI_SERVICE_URL embeddings endpoint
        call_args = mock_client.post.call_args
        assert "/api/embed" in call_args[0][0]

    @patch("app.utils.ai_utils.ai_utils.httpx.AsyncClient")
    def test_embed_service_unavailable(self, mock_client_cls, client):
        import httpx

        mock_client = AsyncMock()
        mock_client.post.side_effect = httpx.RequestError("connection refused")
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client_cls.return_value = mock_client

        response = client.post("/embed", json={"prompt": "test"})
        assert response.status_code == 503


class TestGenerateEndpoint:
    @patch("app.routers.ai.get_similar_publications")
    @patch("app.routers.ai.httpx.AsyncClient")
    def test_generate_success(self, mock_client_cls, mock_get_pubs, client):
        mock_get_pubs.return_value = [
            {"doi": "10.1/a", "title": "Paper A", "year": 2024,
             "category": "article", "abstract": "Abstract text"},
        ]

        mock_stream = _MockStream(lines=[
            '{"message":{"content":"Based on"},"done":false}',
            '{"message":{"content":""},"done":true}',
        ])
        mock_client = AsyncMock()
        mock_client.stream = MagicMock(return_value=mock_stream)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client_cls.return_value = mock_client

        response = client.post("/generate", json={
            "prompt": "What does this researcher study?",
            "entity": {"id": "p1", "type": "person", "label": "John Doe"},
        })
        assert response.status_code == 200
        assert "text/event-stream" in response.headers["content-type"]

    @patch("app.routers.ai.get_similar_publications")
    @patch("app.routers.ai.httpx.AsyncClient")
    def test_generate_without_entity(self, mock_client_cls, mock_get_pubs, client):
        mock_get_pubs.return_value = []

        mock_stream = _MockStream(lines=[
            '{"message":{"content":"answer"},"done":true}',
        ])
        mock_client = AsyncMock()
        mock_client.stream = MagicMock(return_value=mock_stream)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client_cls.return_value = mock_client

        response = client.post("/generate", json={"prompt": "general question"})
        assert response.status_code == 200

    def test_generate_empty_prompt_returns_400(self, client):
        response = client.post("/generate", json={"prompt": "  "})
        assert response.status_code == 400

    def test_generate_missing_prompt(self, client):
        response = client.post("/generate", json={})
        assert response.status_code == 422

    @patch("app.routers.ai.get_similar_publications")
    @patch("app.routers.ai.httpx.AsyncClient")
    def test_generate_passes_entity_to_rag(self, mock_client_cls, mock_get_pubs, client):
        mock_get_pubs.return_value = []

        mock_stream = _MockStream(lines=['{"message":{"content":""},"done":true}'])
        mock_client = AsyncMock()
        mock_client.stream = MagicMock(return_value=mock_stream)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client_cls.return_value = mock_client

        client.post("/generate", json={
            "prompt": "test",
            "entity": {"id": "o1", "type": "organization", "label": "UU"},
            "top_k": 5,
        })

        # Verify get_similar_publications was called with the right args
        call_args = mock_get_pubs.call_args
        assert call_args[0][0] == "test"  # prompt
        assert call_args[0][1].id == "o1"  # entity
        assert call_args[0][1].type == "organization"
        assert call_args[0][2] == 5  # top_k

    @patch("app.routers.ai.get_similar_publications")
    def test_generate_reraises_http_exception(self, mock_get_pubs, client):
        """When get_similar_publications raises HTTPException, it should pass through."""
        from fastapi import HTTPException
        mock_get_pubs.side_effect = HTTPException(status_code=404, detail="Model not found")
        response = client.post("/generate", json={"prompt": "test question"})
        assert response.status_code == 404

    @patch("app.routers.ai.get_similar_publications")
    def test_generate_generic_error_returns_503(self, mock_get_pubs, client):
        """When get_similar_publications raises an unexpected error, return 503."""
        mock_get_pubs.side_effect = RuntimeError("Neo4j connection lost")
        response = client.post("/generate", json={"prompt": "test question"})
        assert response.status_code == 503
        assert "RAG retrieval failed" in response.json()["detail"]


class TestRagHelpers:
    def test_format_similar_publications_for_rag(self):
        from app.routers.ai import format_similar_publications_for_rag

        pubs = [
            {"doi": "10.1/a", "title": "Paper A", "year": 2024,
             "category": "article", "abstract": "The abstract"},
            {"doi": "10.1/b", "title": "Paper B", "year": 2023,
             "category": None, "abstract": None},
        ]
        result = format_similar_publications_for_rag(pubs)
        assert "DOI: 10.1/a" in result
        assert "Abstract: The abstract" in result
        assert "DOI: 10.1/b" in result
        # Second pub has no category/abstract, those fields should be absent
        lines = result.split("\n\n")
        assert "Category:" not in lines[1]
        assert "Abstract:" not in lines[1]

    def test_format_similar_publications_empty(self):
        from app.routers.ai import format_similar_publications_for_rag
        assert format_similar_publications_for_rag([]) == ""

    def test_format_entity_context_person(self):
        from app.routers.ai import format_entity_context
        result = format_entity_context(EntityRef(id="p1", type="person", label="John"))
        assert "person" in result
        assert "John" in result

    def test_format_entity_context_organization(self):
        from app.routers.ai import format_entity_context
        result = format_entity_context(EntityRef(id="o1", type="organization", label="UU"))
        assert "organization" in result
        assert "UU" in result

    def test_build_rag_system_prompt_with_entity_and_pubs(self):
        from app.routers.ai import _build_rag_system_prompt
        entity = EntityRef(id="p1", type="person", label="John")
        prompt = _build_rag_system_prompt(entity, "DOI: 10.1/a | Title: Paper")
        assert "person" in prompt
        assert "John" in prompt
        assert "DOI: 10.1/a" in prompt
        assert "evidence" in prompt.lower()

    def test_build_rag_system_prompt_without_entity(self):
        from app.routers.ai import _build_rag_system_prompt
        prompt = _build_rag_system_prompt(None, "some context")
        assert "some context" in prompt

    def test_build_rag_system_prompt_no_publications(self):
        from app.routers.ai import _build_rag_system_prompt
        entity = EntityRef(id="p1", type="person", label="John")
        prompt = _build_rag_system_prompt(entity, "")
        assert "No publications" in prompt

    def test_vector_search_multiplier_constant(self):
        from app.routers.ai import VECTOR_SEARCH_MULTIPLIER
        assert isinstance(VECTOR_SEARCH_MULTIPLIER, int)
        assert VECTOR_SEARCH_MULTIPLIER > 1


class TestGetSimilarPublications:
    @pytest.mark.asyncio
    async def test_ai_service_down(self):
        from app.routers.ai import get_similar_publications
        with patch("app.routers.ai.async_embed", new_callable=AsyncMock) as mock_embed:
            mock_embed.side_effect = HTTPException(status_code=503, detail="AI service down")
            with pytest.raises(HTTPException, match="503"):
                await get_similar_publications("test prompt", None, top_k=5)

    @pytest.mark.asyncio
    async def test_empty_results(self):
        from app.routers.ai import get_similar_publications
        mock_session = MagicMock()
        mock_session.run.return_value = iter([])
        mock_driver = MagicMock()
        mock_driver.session.return_value.__enter__ = MagicMock(return_value=mock_session)
        mock_driver.session.return_value.__exit__ = MagicMock(return_value=False)

        with patch("app.routers.ai.async_embed", new_callable=AsyncMock, return_value=[0.1] * 768), \
             patch("app.routers.ai.get_graph", return_value=mock_driver):
            result = await get_similar_publications("test", None, top_k=5)
            assert result == []

    @pytest.mark.asyncio
    async def test_person_scoped(self):
        from app.routers.ai import get_similar_publications
        entity = EntityRef(id="person-123", type="person", label="Test Person")
        mock_session = MagicMock()
        mock_session.run.return_value = iter([])
        mock_driver = MagicMock()
        mock_driver.session.return_value.__enter__ = MagicMock(return_value=mock_session)
        mock_driver.session.return_value.__exit__ = MagicMock(return_value=False)

        with patch("app.routers.ai.async_embed", new_callable=AsyncMock, return_value=[0.1] * 768), \
             patch("app.routers.ai.get_graph", return_value=mock_driver):
            await get_similar_publications("test", entity, top_k=5)
            call_args = mock_session.run.call_args
            assert "entityId" in call_args.kwargs or "entityId" in str(call_args)
