"""Tests for RAG helper functions and get_similar_publications."""

from unittest.mock import patch, MagicMock, AsyncMock
import pytest
from fastapi import HTTPException

from app.utils.schemas.ai import EntityRef


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
        # Numbered document format for citation-aware models
        assert "Document [1]" in result
        assert "Document [2]" in result
        assert "DOI: 10.1/a" in result
        assert "Abstract: The abstract" in result
        assert "DOI: 10.1/b" in result
        # Second document block has no category/abstract
        blocks = result.split("\n\n")
        assert "Category:" not in blocks[1]
        assert "Abstract:" not in blocks[1]

    def test_format_similar_publications_single_doc(self):
        from app.routers.ai import format_similar_publications_for_rag
        pubs = [{"doi": "10.1/x", "title": "T", "year": 2024, "category": None, "abstract": None}]
        result = format_similar_publications_for_rag(pubs)
        assert result.startswith("Document [1]")
        assert "\n\n" not in result  # single doc has no block separator

    def test_format_similar_publications_preserves_document_order(self):
        from app.routers.ai import format_similar_publications_for_rag
        pubs = [
            {"doi": f"10.1/{i}", "title": f"T{i}", "year": 2020+i, "category": None, "abstract": None}
            for i in range(5)
        ]
        result = format_similar_publications_for_rag(pubs)
        for i in range(1, 6):
            assert f"Document [{i}]" in result

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
