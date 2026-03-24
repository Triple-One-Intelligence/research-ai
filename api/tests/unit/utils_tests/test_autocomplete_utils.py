"""Tests for autocomplete utility logic."""

from unittest.mock import MagicMock, patch
import pytest
from neo4j.exceptions import ServiceUnavailable

from app.utils.ricgraph_utils.autocomplete import (
    get_autocomplete_suggestions,
    AutocompleteError,
    InvalidQueryError,
)


# ── Validation ───────────────────────────────────────────────────────────────

class TestValidation:
    def test_short_query_raises_invalid_query_error(self):
        with pytest.raises(InvalidQueryError, match="at least 2 characters"):
            get_autocomplete_suggestions("a")

    def test_empty_query_raises_invalid_query_error(self):
        with pytest.raises(InvalidQueryError, match="at least 2 characters"):
            get_autocomplete_suggestions("")

    def test_whitespace_only_raises_invalid_query_error(self):
        with pytest.raises(InvalidQueryError, match="at least 2 characters"):
            get_autocomplete_suggestions("   ")

    def test_none_input_raises_invalid_query_error(self):
        """None as user_query should trigger the `or ""` fallback and raise."""
        with pytest.raises(InvalidQueryError, match="at least 2 characters"):
            get_autocomplete_suggestions(None)


# ── Happy path ───────────────────────────────────────────────────────────────

class TestHappyPath:
    @patch("app.utils.ricgraph_utils.autocomplete.utils.query_utils")
    @patch("app.utils.ricgraph_utils.autocomplete.utils.database_utils")
    def test_returns_persons(self, mock_db, mock_qu):
        mock_qu.normalize_query_for_index.return_value = "henk"
        mock_qu.build_lucene_query.return_value = "henk*"
        mock_db.get_graph.return_value.execute_query.return_value = [
            {"id": "p1", "displayName": "Henk Boer", "type": "person", "bestScore": 100},
        ]
        mock_db.FULLTEXT_INDEX_NAME = "idx"

        result = get_autocomplete_suggestions("henk")
        assert len(result.persons) == 1
        assert result.persons[0].author_id == "p1"
        assert result.persons[0].name == "Henk Boer"
        assert result.organizations == []

    @patch("app.utils.ricgraph_utils.autocomplete.utils.query_utils")
    @patch("app.utils.ricgraph_utils.autocomplete.utils.database_utils")
    def test_returns_organizations(self, mock_db, mock_qu):
        mock_qu.normalize_query_for_index.return_value = "utrecht"
        mock_qu.build_lucene_query.return_value = "utrecht*"
        mock_db.get_graph.return_value.execute_query.return_value = [
            {"id": "o1", "displayName": "Utrecht University", "type": "organization", "bestScore": 50},
        ]
        mock_db.FULLTEXT_INDEX_NAME = "idx"

        result = get_autocomplete_suggestions("utrecht")
        assert len(result.organizations) == 1
        assert result.organizations[0].organization_id == "o1"
        assert result.persons == []

    @patch("app.utils.ricgraph_utils.autocomplete.utils.query_utils")
    @patch("app.utils.ricgraph_utils.autocomplete.utils.database_utils")
    def test_returns_mixed_results(self, mock_db, mock_qu):
        mock_qu.normalize_query_for_index.return_value = "smith"
        mock_qu.build_lucene_query.return_value = "smith*"
        mock_db.get_graph.return_value.execute_query.return_value = [
            {"id": "p1", "displayName": "John Smith", "type": "person", "bestScore": 100},
            {"id": "o1", "displayName": "Smith Corp", "type": "organization", "bestScore": 50},
        ]
        mock_db.FULLTEXT_INDEX_NAME = "idx"

        result = get_autocomplete_suggestions("smith")
        assert len(result.persons) == 1
        assert len(result.organizations) == 1

    @patch("app.utils.ricgraph_utils.autocomplete.utils.query_utils")
    @patch("app.utils.ricgraph_utils.autocomplete.utils.database_utils")
    def test_empty_result_returns_empty_suggestions(self, mock_db, mock_qu):
        mock_qu.normalize_query_for_index.return_value = "nobody"
        mock_qu.build_lucene_query.return_value = "nobody*"
        mock_db.get_graph.return_value.execute_query.return_value = []
        mock_db.FULLTEXT_INDEX_NAME = "idx"

        result = get_autocomplete_suggestions("nobody")
        assert result.persons == []
        assert result.organizations == []


# ── Parameters ───────────────────────────────────────────────────────────────

class TestParameters:
    @patch("app.utils.ricgraph_utils.autocomplete.utils.query_utils")
    @patch("app.utils.ricgraph_utils.autocomplete.utils.database_utils")
    def test_query_params_passed_correctly(self, mock_db, mock_qu):
        """Verify keywords, firstKeyword, cleanQuery, limit are built correctly."""
        mock_qu.normalize_query_for_index.return_value = "henk boer"
        mock_qu.build_lucene_query.return_value = "henk* AND boer*"
        mock_db.get_graph.return_value.execute_query.return_value = []
        mock_db.FULLTEXT_INDEX_NAME = "idx"

        get_autocomplete_suggestions("Henk Boer", limit=5)

        call_kwargs = mock_db.get_graph.return_value.execute_query.call_args.kwargs
        assert call_kwargs["keywords"] == ["henk", "boer"]
        assert call_kwargs["firstKeyword"] == "henk"
        assert call_kwargs["cleanQuery"] == "henk boer"
        assert call_kwargs["luceneQuery"] == "henk* AND boer*"
        assert call_kwargs["indexName"] == "idx"
        assert call_kwargs["limit"] == 5


# ── Error handling ───────────────────────────────────────────────────────────

class TestErrorHandling:
    @patch("app.utils.ricgraph_utils.autocomplete.utils.query_utils")
    @patch("app.utils.ricgraph_utils.autocomplete.utils.database_utils")
    def test_service_unavailable_propagates(self, mock_db, mock_qu):
        """ServiceUnavailable should not be wrapped — it propagates directly."""
        mock_qu.normalize_query_for_index.return_value = "test query"
        mock_qu.build_lucene_query.return_value = "test*"
        mock_db.get_graph.return_value.execute_query.side_effect = ServiceUnavailable("neo4j down")
        mock_db.FULLTEXT_INDEX_NAME = "idx"

        with pytest.raises(ServiceUnavailable):
            get_autocomplete_suggestions("test query")

    @patch("app.utils.ricgraph_utils.autocomplete.utils.query_utils")
    @patch("app.utils.ricgraph_utils.autocomplete.utils.database_utils")
    def test_runtime_error_propagates(self, mock_db, mock_qu):
        """RuntimeError (e.g. driver not initialized) should propagate directly."""
        mock_qu.normalize_query_for_index.return_value = "test query"
        mock_qu.build_lucene_query.return_value = "test*"
        mock_db.get_graph.return_value.execute_query.side_effect = RuntimeError("no driver")
        mock_db.FULLTEXT_INDEX_NAME = "idx"

        with pytest.raises(RuntimeError, match="no driver"):
            get_autocomplete_suggestions("test query")

    @patch("app.utils.ricgraph_utils.autocomplete.utils.query_utils")
    @patch("app.utils.ricgraph_utils.autocomplete.utils.database_utils")
    def test_generic_exception_wrapped_in_autocomplete_error(self, mock_db, mock_qu):
        """Other exceptions should be wrapped in AutocompleteError."""
        mock_qu.normalize_query_for_index.return_value = "test query"
        mock_qu.build_lucene_query.return_value = "test*"
        mock_db.get_graph.return_value.execute_query.side_effect = TypeError("something weird")
        mock_db.FULLTEXT_INDEX_NAME = "idx"

        with pytest.raises(AutocompleteError, match="Autocomplete query failed"):
            get_autocomplete_suggestions("test query")

    @patch("app.utils.ricgraph_utils.autocomplete.utils.query_utils")
    @patch("app.utils.ricgraph_utils.autocomplete.utils.database_utils")
    def test_unknown_type_raises_autocomplete_error(self, mock_db, mock_qu):
        mock_qu.normalize_query_for_index.return_value = "test"
        mock_qu.build_lucene_query.return_value = "test*"
        mock_db.get_graph.return_value.execute_query.return_value = [
            {"id": "x1", "displayName": "Thing", "type": "alien", "bestScore": 10},
        ]
        mock_db.FULLTEXT_INDEX_NAME = "idx"

        with pytest.raises(AutocompleteError, match="Unexpected type"):
            get_autocomplete_suggestions("test")


# ── Edge cases ───────────────────────────────────────────────────────────────

class TestEdgeCases:
    @patch("app.utils.ricgraph_utils.autocomplete.utils.query_utils")
    @patch("app.utils.ricgraph_utils.autocomplete.utils.database_utils")
    def test_whitespace_tokens_return_empty(self, mock_db, mock_qu):
        """If normalization results in all-empty tokens, return empty Suggestions."""
        mock_qu.normalize_query_for_index.return_value = "   "
        result = get_autocomplete_suggestions("  ab  ")
        assert result.persons == []
        assert result.organizations == []
        mock_db.get_graph.assert_not_called()
