"""Tests for pipeline budget logic, context helpers, and the /pipeline endpoint."""

import pytest
from unittest.mock import patch, AsyncMock, MagicMock
from fastapi.responses import StreamingResponse
from fastapi.testclient import TestClient

from app.utils.schemas.ai import EntityRef
from app.pipelines.budget import tokens, fit_publications, fit_ranked_lines, data_budget, INPUT_BUDGET
from app.pipelines.contexts import _pub_blocks


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def entity(type_="person"):
    return EntityRef(id="test-id", type=type_, label="Test Entity")


# ---------------------------------------------------------------------------
# tokens()
# ---------------------------------------------------------------------------

class TestTokens:
    def test_empty_string(self):
        assert tokens("") == 0

    def test_approximation(self):
        # 4 chars = 1 token
        assert tokens("abcd") == 1
        assert tokens("abcdefgh") == 2

    def test_remainder_truncated(self):
        # 5 chars → 1 token (floor division)
        assert tokens("abcde") == 1

    def test_long_text(self):
        text = "word " * 100  # 500 chars
        assert tokens(text) == 125


# ---------------------------------------------------------------------------
# fit_ranked_lines()
# ---------------------------------------------------------------------------

class TestFitRankedLines:
    def test_all_fit(self):
        lines = ["1. Alpha", "2. Beta", "3. Gamma"]
        result = fit_ranked_lines(lines, budget=1000)
        assert result == lines

    def test_empty_input(self):
        assert fit_ranked_lines([], budget=1000) == []

    def test_zero_budget(self):
        assert fit_ranked_lines(["1. Alpha"], budget=0) == []

    def test_trims_from_bottom(self):
        lines = ["1. First", "2. Second", "3. Third"]
        # Each line is ~2 tokens. Budget of 4 fits two lines.
        result = fit_ranked_lines(lines, budget=4)
        assert result[0] == "1. First"
        assert "3. Third" not in result

    def test_exact_fit(self):
        line = "a" * 4  # exactly 1 token
        result = fit_ranked_lines([line], budget=1)
        assert result == [line]

    def test_one_over_budget(self):
        line = "a" * 8  # 2 tokens
        result = fit_ranked_lines([line], budget=1)
        assert result == []


# ---------------------------------------------------------------------------
# fit_publications()
# ---------------------------------------------------------------------------

class TestFitPublications:
    def _pub(self, title="Title", abstract="Abstract text here."):
        core = f"DOI: 10.1/test\nTitle: {title}"
        return (core, f"Abstract: {abstract}")

    def test_all_fit(self):
        pubs = [self._pub("Paper A"), self._pub("Paper B")]
        result = fit_publications(pubs, budget=10000)
        assert len(result) == 2
        assert "Abstract" in result[0]

    def test_empty_input(self):
        assert fit_publications([], budget=1000) == []

    def test_zero_budget(self):
        assert fit_publications([self._pub()], budget=0) == []

    def test_negative_budget(self):
        assert fit_publications([self._pub()], budget=-1) == []

    def test_stage1_strips_abstracts_from_tail(self):
        # 3 publications, tight budget — stage 1 should strip abstracts from least important first
        long_abstract = "x" * 400  # 100 tokens each
        pubs = [
            ("DOI: 10.1/a\nTitle: A", f"Abstract: {long_abstract}"),
            ("DOI: 10.1/b\nTitle: B", f"Abstract: {long_abstract}"),
            ("DOI: 10.1/c\nTitle: C", f"Abstract: {long_abstract}"),
        ]
        # Budget enough for cores + 1 abstract
        budget = tokens("DOI: 10.1/a\nTitle: A") * 3 + 110
        result = fit_publications(pubs, budget=budget)
        assert len(result) >= 1
        # First entry should keep its abstract
        assert "Abstract" in result[0]
        # Last entry should have abstract stripped if budget was tight
        if len(result) == 3:
            assert "Abstract" not in result[-1]

    def test_stage2_drops_from_tail(self):
        # Very tight budget — only first publication should survive
        long_core = "x" * 400  # 100 tokens
        pubs = [(long_core, ""), (long_core, ""), (long_core, "")]
        budget = tokens(long_core) + 5
        result = fit_publications(pubs, budget=budget)
        assert len(result) == 1

    def test_preserves_order(self):
        pubs = [
            ("DOI: 10.1/first\nTitle: First", "Abstract: First abstract."),
            ("DOI: 10.1/second\nTitle: Second", "Abstract: Second abstract."),
        ]
        result = fit_publications(pubs, budget=10000)
        assert "First" in result[0]
        assert "Second" in result[1]

    def test_pub_without_abstract(self):
        pubs = [("DOI: 10.1/test\nTitle: Paper", "")]
        result = fit_publications(pubs, budget=1000)
        assert len(result) == 1
        assert "Abstract:" not in result[0]


# ---------------------------------------------------------------------------
# data_budget()
# ---------------------------------------------------------------------------

class TestDataBudget:
    def test_budget_less_than_input_budget(self):
        # Fixed overhead (system prompt + entity context + prompt) is subtracted
        e = entity()
        budget = data_budget(e, "Tell me about their research.")
        assert budget < INPUT_BUDGET
        assert budget > 0

    def test_longer_prompt_reduces_budget(self):
        e = entity()
        short = data_budget(e, "Hi")
        long = data_budget(e, "x" * 1000)
        assert long < short

    def test_person_vs_org_same_label(self):
        # Entity type affects format_entity_context output minimally
        person_budget = data_budget(entity("person"), "test")
        org_budget = data_budget(entity("organization"), "test")
        # Both should be reasonable positive values
        assert person_budget > 0
        assert org_budget > 0


# ---------------------------------------------------------------------------
# _pub_blocks()
# ---------------------------------------------------------------------------

class TestPubBlocks:
    def test_single_block(self):
        result = _pub_blocks(["DOI: 10.1/a\nTitle: A\nAbstract: X"])
        assert result == "Document [1]\nDOI: 10.1/a\nTitle: A\nAbstract: X"

    def test_multiple_blocks_numbered(self):
        result = _pub_blocks(["Block A", "Block B", "Block C"])
        assert "Document [1]" in result
        assert "Document [2]" in result
        assert "Document [3]" in result

    def test_blocks_separated_by_double_newline(self):
        result = _pub_blocks(["A", "B"])
        assert result == "Document [1]\nA\n\nDocument [2]\nB"

    def test_empty_input(self):
        assert _pub_blocks([]) == ""


# ---------------------------------------------------------------------------
# _llm_payload()
# ---------------------------------------------------------------------------

class TestLlmPayload:
    def setup_method(self):
        from app.routers.pipeline import _llm_payload
        self._llm_payload = _llm_payload

    def test_message_structure(self):
        payload = self._llm_payload("sys", "user")
        assert payload["messages"][0] == {"role": "system", "content": "sys"}
        assert payload["messages"][1] == {"role": "user", "content": "user"}

    def test_streaming_enabled(self):
        assert self._llm_payload("s", "u")["stream"] is True

    def test_num_ctx_passed(self):
        # Critical: without num_ctx Ollama defaults to 4096 and silently truncates context
        from app.config import CHAT_CONTEXT_WINDOW
        payload = self._llm_payload("s", "u")
        assert payload["options"]["num_ctx"] == CHAT_CONTEXT_WINDOW

    def test_num_predict_passed(self):
        from app.config import CHAT_MAX_TOKENS
        payload = self._llm_payload("s", "u")
        assert payload["options"]["num_predict"] == CHAT_MAX_TOKENS

    def test_model_set(self):
        from app.config import CHAT_MODEL
        assert self._llm_payload("s", "u")["model"] == CHAT_MODEL


# ---------------------------------------------------------------------------
# /pipeline/{prompt_type} endpoint
# ---------------------------------------------------------------------------

@pytest.fixture
def client():
    with patch("app.utils.database_utils.database_utils.startup"):
        with patch("app.utils.database_utils.database_utils.shutdown"):
            from app.main import app
            with TestClient(app, raise_server_exceptions=False) as c:
                yield c


ENTITY_PAYLOAD = {"id": "test-id", "type": "person", "label": "Test Person"}


class TestPipelineEndpointValidation:
    def test_unknown_prompt_type_returns_404(self, client):
        resp = client.post("/pipeline/unknownType", json={"prompt": "test", "entity": ENTITY_PAYLOAD})
        assert resp.status_code == 404

    def test_empty_prompt_returns_400(self, client):
        resp = client.post("/pipeline/executiveSummary", json={"prompt": "   ", "entity": ENTITY_PAYLOAD})
        assert resp.status_code == 400

    def test_missing_entity_returns_422(self, client):
        resp = client.post("/pipeline/executiveSummary", json={"prompt": "test"})
        assert resp.status_code == 422

    def test_missing_prompt_returns_422(self, client):
        resp = client.post("/pipeline/executiveSummary", json={"entity": ENTITY_PAYLOAD})
        assert resp.status_code == 422

    def test_invalid_entity_type_returns_422(self, client):
        bad_entity = {"id": "x", "type": "robot", "label": "R2D2"}
        resp = client.post("/pipeline/executiveSummary", json={"prompt": "test", "entity": bad_entity})
        assert resp.status_code == 422

    @pytest.mark.parametrize("prompt_type", [
        "executiveSummary", "topOrganizations", "topCollaborators", "recentPublications"
    ])
    def test_all_valid_types_accepted(self, client, prompt_type):
        # Context builders and Ollama are mocked — we just verify routing doesn't 404
        with patch("app.routers.pipeline.executive_summary_context", new=AsyncMock(return_value="sys")), \
             patch("app.routers.pipeline.top_organizations_context", return_value="sys"), \
             patch("app.routers.pipeline.top_collaborators_context", return_value="sys"), \
             patch("app.routers.pipeline.recent_publications_context", return_value="sys"), \
             patch("app.routers.pipeline._stream_ollama") as mock_ollama:
            mock_ollama.return_value = StreamingResponse(iter([]), media_type="text/event-stream")
            resp = client.post(f"/pipeline/{prompt_type}", json={"prompt": "test", "entity": ENTITY_PAYLOAD})
            assert resp.status_code != 404

    def test_context_failure_returns_503(self, client):
        with patch("app.routers.pipeline.executive_summary_context", new=AsyncMock(side_effect=RuntimeError("db down"))):
            resp = client.post("/pipeline/executiveSummary", json={"prompt": "test", "entity": ENTITY_PAYLOAD})
            assert resp.status_code == 503

    def test_ollama_error_does_not_leak_internals(self, client):
        # When Ollama is unreachable the streamed error must not contain internal URLs or exception details
        import httpx

        mock_stream_cm = AsyncMock()
        mock_stream_cm.__aenter__.side_effect = httpx.RequestError("http://internal-host:11434 refused")

        mock_http_client = AsyncMock()
        mock_http_client.__aenter__.return_value = mock_http_client
        mock_http_client.__aexit__ = AsyncMock(return_value=False)
        mock_http_client.stream = MagicMock(return_value=mock_stream_cm)  # sync method, not async

        with patch("app.routers.pipeline.executive_summary_context", new=AsyncMock(return_value="sys")), \
             patch("httpx.AsyncClient", return_value=mock_http_client):
            resp = client.post("/pipeline/executiveSummary", json={"prompt": "test", "entity": ENTITY_PAYLOAD})
            assert "internal-host" not in resp.text
            assert "11434" not in resp.text
            assert "AI service unavailable" in resp.text

    def test_malformed_ollama_line_is_skipped(self, client):
        # A non-JSON line from Ollama must not kill the stream — subsequent tokens should still arrive
        import json as json_mod

        lines_to_stream = [
            "not-valid-json",
            json_mod.dumps({"message": {"content": "hello"}, "done": False}),
            json_mod.dumps({"done": True}),
        ]

        async def fake_aiter_lines():
            for line in lines_to_stream:
                yield line

        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_resp.aiter_lines = fake_aiter_lines  # async generator function, not AsyncMock

        mock_stream_cm = AsyncMock()
        mock_stream_cm.__aenter__.return_value = mock_resp
        mock_stream_cm.__aexit__ = AsyncMock(return_value=False)

        mock_http_client = AsyncMock()
        mock_http_client.__aenter__.return_value = mock_http_client
        mock_http_client.__aexit__ = AsyncMock(return_value=False)
        mock_http_client.stream = MagicMock(return_value=mock_stream_cm)  # sync method, not async

        with patch("app.routers.pipeline.executive_summary_context", new=AsyncMock(return_value="sys")), \
             patch("httpx.AsyncClient", return_value=mock_http_client):
            resp = client.post("/pipeline/executiveSummary", json={"prompt": "test", "entity": ENTITY_PAYLOAD})
            assert "hello" in resp.text

    @pytest.mark.parametrize("prompt_type,expected_fn", [
        ("executiveSummary",    "executive_summary_context"),
        ("topOrganizations",    "top_organizations_context"),
        ("topCollaborators",    "top_collaborators_context"),
        ("recentPublications",  "recent_publications_context"),
    ])
    def test_correct_context_function_called(self, client, prompt_type, expected_fn):
        fn_names = ["executive_summary_context", "top_organizations_context", "top_collaborators_context", "recent_publications_context"]
        patches = {k: AsyncMock(return_value="sys") if k == "executive_summary_context" else MagicMock(return_value="sys")
                   for k in fn_names}

        with patch("app.routers.pipeline.executive_summary_context",  new=patches["executive_summary_context"]), \
             patch("app.routers.pipeline.top_organizations_context",   new=patches["top_organizations_context"]), \
             patch("app.routers.pipeline.top_collaborators_context",   new=patches["top_collaborators_context"]), \
             patch("app.routers.pipeline.recent_publications_context", new=patches["recent_publications_context"]), \
             patch("app.routers.pipeline._stream_ollama", return_value=StreamingResponse(iter([]), media_type="text/event-stream")):
            client.post(f"/pipeline/{prompt_type}", json={"prompt": "test", "entity": ENTITY_PAYLOAD})

        patches[expected_fn].assert_called_once()
        for fn_name, mock in patches.items():
            if fn_name != expected_fn:
                mock.assert_not_called()
