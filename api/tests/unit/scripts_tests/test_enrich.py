"""Tests for the enrichment pipeline (abstract fetching, embedding, storage)."""

from unittest.mock import MagicMock, patch, call
import pytest
import httpx

from app.scripts.enrich import (
    reconstruct_abstract,
    fetch_abstract,
    generate_embedding,
    find_publication_dois,
    store_enrichment,
    run,
    main,
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
    def test_returns_embedding_vector_new_api(self):
        """New /api/embed endpoint returns {"embeddings": [[...]]}."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"embeddings": [[0.1, 0.2, 0.3]]}
        mock_response.raise_for_status = MagicMock()

        client = MagicMock()
        client.post.return_value = mock_response

        result = generate_embedding("test text", client)
        assert result == [0.1, 0.2, 0.3]

    def test_falls_back_to_legacy_api(self):
        """Falls back to /api/embeddings when /api/embed returns 404."""
        not_found = MagicMock()
        not_found.status_code = 404

        legacy_resp = MagicMock()
        legacy_resp.json.return_value = {"embedding": [0.4, 0.5, 0.6]}
        legacy_resp.raise_for_status = MagicMock()

        client = MagicMock()
        client.post.side_effect = [not_found, legacy_resp]

        result = generate_embedding("test text", client)
        assert result == [0.4, 0.5, 0.6]

    def test_returns_none_on_error(self):
        client = MagicMock()
        client.post.side_effect = httpx.HTTPError("connection refused")

        result = generate_embedding("test text", client)
        assert result is None

    def test_returns_none_when_no_embedding_key(self):
        mock_response = MagicMock()
        mock_response.status_code = 200
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


class TestRun:
    @patch("app.scripts.enrich.AI_SERVICE_URL", "")
    def test_exits_when_no_ai_service_url(self):
        with pytest.raises(SystemExit, match="1"):
            run()

    @patch("app.scripts.enrich.time.sleep")
    @patch("app.scripts.enrich.AI_SERVICE_URL", "http://ai:11434")
    @patch("app.scripts.enrich.EMBED_DIMENSIONS", 768)
    @patch("app.scripts.enrich.database_utils")
    def test_returns_early_when_no_publications(self, mock_db, mock_sleep):
        mock_driver = MagicMock()
        mock_db.get_graph.return_value = mock_driver

        mock_session = MagicMock()
        mock_session.run.return_value = []
        mock_driver.session.return_value.__enter__ = MagicMock(return_value=mock_session)
        mock_driver.session.return_value.__exit__ = MagicMock(return_value=False)

        run(force=False)

        mock_db.connect_to_database.assert_called_once()
        mock_db.ensure_vector_index.assert_called_once_with(mock_driver, 768)
        mock_driver.close.assert_called_once()

    @patch("app.scripts.enrich.time.sleep")
    @patch("app.scripts.enrich.store_enrichment")
    @patch("app.scripts.enrich.generate_embedding")
    @patch("app.scripts.enrich.fetch_abstract")
    @patch("app.scripts.enrich.find_publication_dois")
    @patch("app.scripts.enrich.AI_SERVICE_URL", "http://ai:11434")
    @patch("app.scripts.enrich.EMBED_DIMENSIONS", 768)
    @patch("app.scripts.enrich.database_utils")
    def test_enriches_publications(
        self, mock_db, mock_find, mock_fetch, mock_embed, mock_store, mock_sleep
    ):
        mock_driver = MagicMock()
        mock_db.get_graph.return_value = mock_driver
        mock_find.return_value = ["10.1/a", "10.1/b"]
        mock_fetch.side_effect = ["Abstract A", "Abstract B"]
        mock_embed.side_effect = [[0.1, 0.2], [0.3, 0.4]]

        run(force=False)

        assert mock_store.call_count == 2
        mock_store.assert_any_call(mock_driver, "10.1/a", "Abstract A", [0.1, 0.2])
        mock_store.assert_any_call(mock_driver, "10.1/b", "Abstract B", [0.3, 0.4])
        mock_driver.close.assert_called_once()

    @patch("app.scripts.enrich.time.sleep")
    @patch("app.scripts.enrich.store_enrichment")
    @patch("app.scripts.enrich.generate_embedding")
    @patch("app.scripts.enrich.fetch_abstract")
    @patch("app.scripts.enrich.find_publication_dois")
    @patch("app.scripts.enrich.AI_SERVICE_URL", "http://ai:11434")
    @patch("app.scripts.enrich.EMBED_DIMENSIONS", 768)
    @patch("app.scripts.enrich.database_utils")
    def test_skips_when_no_abstract(
        self, mock_db, mock_find, mock_fetch, mock_embed, mock_store, mock_sleep
    ):
        mock_driver = MagicMock()
        mock_db.get_graph.return_value = mock_driver
        mock_find.return_value = ["10.1/a"]
        mock_fetch.return_value = None

        run(force=False)

        mock_embed.assert_not_called()
        mock_store.assert_not_called()
        mock_driver.close.assert_called_once()

    @patch("app.scripts.enrich.time.sleep")
    @patch("app.scripts.enrich.store_enrichment")
    @patch("app.scripts.enrich.generate_embedding")
    @patch("app.scripts.enrich.fetch_abstract")
    @patch("app.scripts.enrich.find_publication_dois")
    @patch("app.scripts.enrich.AI_SERVICE_URL", "http://ai:11434")
    @patch("app.scripts.enrich.EMBED_DIMENSIONS", 768)
    @patch("app.scripts.enrich.database_utils")
    def test_skips_when_embedding_fails(
        self, mock_db, mock_find, mock_fetch, mock_embed, mock_store, mock_sleep
    ):
        mock_driver = MagicMock()
        mock_db.get_graph.return_value = mock_driver
        mock_find.return_value = ["10.1/a"]
        mock_fetch.return_value = "An abstract"
        mock_embed.return_value = None

        run(force=False)

        mock_store.assert_not_called()
        mock_driver.close.assert_called_once()

    @patch("app.scripts.enrich.time.sleep")
    @patch("app.scripts.enrich.store_enrichment")
    @patch("app.scripts.enrich.generate_embedding")
    @patch("app.scripts.enrich.fetch_abstract")
    @patch("app.scripts.enrich.find_publication_dois")
    @patch("app.scripts.enrich.AI_SERVICE_URL", "http://ai:11434")
    @patch("app.scripts.enrich.EMBED_DIMENSIONS", 768)
    @patch("app.scripts.enrich.database_utils")
    def test_closes_driver_on_exception(
        self, mock_db, mock_find, mock_fetch, mock_embed, mock_store, mock_sleep
    ):
        mock_driver = MagicMock()
        mock_db.get_graph.return_value = mock_driver
        mock_find.side_effect = RuntimeError("db error")

        with pytest.raises(RuntimeError, match="db error"):
            run(force=False)

        mock_driver.close.assert_called_once()

    @patch("app.scripts.enrich.time.sleep")
    @patch("app.scripts.enrich.store_enrichment")
    @patch("app.scripts.enrich.generate_embedding")
    @patch("app.scripts.enrich.fetch_abstract")
    @patch("app.scripts.enrich.find_publication_dois")
    @patch("app.scripts.enrich.AI_SERVICE_URL", "http://ai:11434")
    @patch("app.scripts.enrich.EMBED_DIMENSIONS", 768)
    @patch("app.scripts.enrich.database_utils")
    def test_batch_pause(
        self, mock_db, mock_find, mock_fetch, mock_embed, mock_store, mock_sleep
    ):
        mock_driver = MagicMock()
        mock_db.get_graph.return_value = mock_driver
        mock_find.return_value = ["10.1/a", "10.1/b"]
        mock_fetch.return_value = "Abstract"
        mock_embed.return_value = [0.1]

        run(force=False, batch_size=1)

        # Each item gets a 0.15s sleep, plus batch pause (1s) after every batch_size items
        sleep_values = [c.args[0] for c in mock_sleep.call_args_list]
        assert 1 in sleep_values


class TestMain:
    @patch("app.scripts.enrich.run")
    def test_parses_defaults(self, mock_run):
        with patch("sys.argv", ["enrich"]):
            main()
        mock_run.assert_called_once_with(force=False, batch_size=50)

    @patch("app.scripts.enrich.run")
    def test_parses_force_and_batch_size(self, mock_run):
        with patch("sys.argv", ["enrich", "--force", "--batch-size", "10"]):
            main()
        mock_run.assert_called_once_with(force=True, batch_size=10)
