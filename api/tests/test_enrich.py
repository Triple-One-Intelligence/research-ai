"""Tests for the enrichment pipeline (abstract fetching, embedding, storage)."""

from unittest.mock import MagicMock, patch
import pytest
import httpx

from app.scripts.enrich import (
    reconstruct_abstract,
    fetch_abstract,
    generate_embedding,
    find_publication_dois,
    store_enrichment,
)


class TestReconstructAbstract:
    def test_basic_reconstruction(self):
        inverted = {"Hello": [0], "world": [1]}
        assert reconstruct_abstract(inverted) == "Hello world"

    def test_ordered_reconstruction(self):
        inverted = {"the": [0, 3], "cat": [1], "sat": [2], "on": [4], "mat": [5]}
        assert reconstruct_abstract(inverted) == "the cat sat the on mat"

    def test_empty_dict_returns_empty(self):
        assert reconstruct_abstract({}) == ""

    def test_none_returns_empty(self):
        assert reconstruct_abstract(None) == ""

    def test_single_word(self):
        assert reconstruct_abstract({"Abstract": [0]}) == "Abstract"

    def test_preserves_word_order_by_position(self):
        inverted = {"banana": [2], "apple": [0], "cherry": [1]}
        assert reconstruct_abstract(inverted) == "apple cherry banana"


class TestFetchAbstract:
    def test_returns_abstract_from_inverted_index(self):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "abstract_inverted_index": {"Test": [0], "abstract": [1]}
        }
        mock_response.raise_for_status = MagicMock()

        client = MagicMock()
        client.get.return_value = mock_response

        result = fetch_abstract("10.1234/test", client)
        assert result == "Test abstract"

    def test_returns_none_on_404(self):
        mock_response = MagicMock()
        mock_response.status_code = 404

        client = MagicMock()
        client.get.return_value = mock_response

        result = fetch_abstract("10.1234/missing", client)
        assert result is None

    def test_returns_none_when_no_inverted_index(self):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"abstract_inverted_index": None}
        mock_response.raise_for_status = MagicMock()

        client = MagicMock()
        client.get.return_value = mock_response

        result = fetch_abstract("10.1234/no-abstract", client)
        assert result is None

    def test_returns_none_on_http_error(self):
        client = MagicMock()
        client.get.side_effect = httpx.HTTPError("timeout")

        result = fetch_abstract("10.1234/error", client)
        assert result is None

    @patch("app.scripts.enrich.OPENALEX_MAILTO", "test@example.com")
    def test_passes_mailto_param(self):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"abstract_inverted_index": {"Hi": [0]}}
        mock_response.raise_for_status = MagicMock()

        client = MagicMock()
        client.get.return_value = mock_response

        fetch_abstract("10.1234/test", client)
        call_kwargs = client.get.call_args
        assert call_kwargs.kwargs["params"]["mailto"] == "test@example.com"


class TestGenerateEmbedding:
    def test_returns_embedding_vector(self):
        mock_response = MagicMock()
        mock_response.json.return_value = {"embedding": [0.1, 0.2, 0.3]}
        mock_response.raise_for_status = MagicMock()

        client = MagicMock()
        client.post.return_value = mock_response

        result = generate_embedding("test text", client)
        assert result == [0.1, 0.2, 0.3]

    def test_returns_none_on_error(self):
        client = MagicMock()
        client.post.side_effect = httpx.HTTPError("connection refused")

        result = generate_embedding("test text", client)
        assert result is None

    def test_returns_none_when_no_embedding_key(self):
        mock_response = MagicMock()
        mock_response.json.return_value = {}
        mock_response.raise_for_status = MagicMock()

        client = MagicMock()
        client.post.return_value = mock_response

        result = generate_embedding("test text", client)
        assert result is None


class TestFindPublicationDois:
    def test_find_dois_normal_mode(self):
        mock_session = MagicMock()
        mock_result = [{"doi": "10.1/a"}, {"doi": "10.1/b"}]
        mock_session.run.return_value = mock_result

        driver = MagicMock()
        driver.session.return_value.__enter__ = MagicMock(return_value=mock_session)
        driver.session.return_value.__exit__ = MagicMock(return_value=False)

        dois = find_publication_dois(driver, force=False)
        assert dois == ["10.1/a", "10.1/b"]
        query = mock_session.run.call_args[0][0]
        assert "abstract IS NULL" in query

    def test_find_dois_force_mode(self):
        mock_session = MagicMock()
        mock_result = [{"doi": "10.1/a"}]
        mock_session.run.return_value = mock_result

        driver = MagicMock()
        driver.session.return_value.__enter__ = MagicMock(return_value=mock_session)
        driver.session.return_value.__exit__ = MagicMock(return_value=False)

        dois = find_publication_dois(driver, force=True)
        assert dois == ["10.1/a"]
        query = mock_session.run.call_args[0][0]
        assert "abstract IS NULL" not in query

    def test_returns_empty_when_no_results(self):
        mock_session = MagicMock()
        mock_session.run.return_value = []

        driver = MagicMock()
        driver.session.return_value.__enter__ = MagicMock(return_value=mock_session)
        driver.session.return_value.__exit__ = MagicMock(return_value=False)

        dois = find_publication_dois(driver, force=False)
        assert dois == []


class TestStoreEnrichment:
    def test_stores_abstract_and_embedding(self):
        mock_session = MagicMock()
        driver = MagicMock()
        driver.session.return_value.__enter__ = MagicMock(return_value=mock_session)
        driver.session.return_value.__exit__ = MagicMock(return_value=False)

        store_enrichment(driver, "10.1/test", "An abstract", [0.1, 0.2])

        mock_session.run.assert_called_once()
        call_kwargs = mock_session.run.call_args
        assert call_kwargs.kwargs["doi"] == "10.1/test"
        assert call_kwargs.kwargs["abstract"] == "An abstract"
        assert call_kwargs.kwargs["embedding"] == [0.1, 0.2]
