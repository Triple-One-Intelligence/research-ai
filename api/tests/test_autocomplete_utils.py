"""Tests for autocomplete utility logic."""

from unittest.mock import MagicMock, patch
import pytest

from app.utils.schemas import Suggestions, Person, Organization


class TestGetAutocompleteSuggestions:
    @patch("app.utils.ricgraph_utils.autocomplete.utils.database_utils")
    def test_short_query_raises_invalid_query_error(self, mock_db):
        from app.utils.ricgraph_utils.autocomplete import (
            get_autocomplete_suggestions,
            InvalidQueryError,
        )

        with pytest.raises(InvalidQueryError, match="at least 2 characters"):
            get_autocomplete_suggestions("a")
        mock_db.get_graph.assert_not_called()

    @patch("app.utils.ricgraph_utils.autocomplete.utils.database_utils")
    def test_empty_query_raises_invalid_query_error(self, mock_db):
        from app.utils.ricgraph_utils.autocomplete import (
            get_autocomplete_suggestions,
            InvalidQueryError,
        )

        with pytest.raises(InvalidQueryError, match="at least 2 characters"):
            get_autocomplete_suggestions("")

    @patch("app.utils.ricgraph_utils.autocomplete.utils.database_utils")
    def test_whitespace_only_raises_invalid_query_error(self, mock_db):
        from app.utils.ricgraph_utils.autocomplete import (
            get_autocomplete_suggestions,
            InvalidQueryError,
        )

        with pytest.raises(InvalidQueryError, match="at least 2 characters"):
            get_autocomplete_suggestions("   ")

    @patch("app.utils.ricgraph_utils.autocomplete.utils.database_utils")
    def test_returns_persons(self, mock_db):
        from app.utils.ricgraph_utils.autocomplete import get_autocomplete_suggestions

        mock_db.execute_cypher.return_value = [
            {"id": "key1", "displayName": "Henk Boer", "type": "person", "bestScore": 100},
        ]
        mock_db.FULLTEXT_INDEX_NAME = "ValueFulltextIndex"

        result = get_autocomplete_suggestions("henk boer")
        assert len(result.persons) == 1
        assert result.persons[0].name == "Henk Boer"
        assert result.persons[0].author_id == "key1"

    @patch("app.utils.ricgraph_utils.autocomplete.utils.database_utils")
    def test_returns_organizations(self, mock_db):
        from app.utils.ricgraph_utils.autocomplete import get_autocomplete_suggestions

        mock_db.execute_cypher.return_value = [
            {"id": "org1", "displayName": "Utrecht University", "type": "organization", "bestScore": 50},
        ]
        mock_db.FULLTEXT_INDEX_NAME = "ValueFulltextIndex"

        result = get_autocomplete_suggestions("utrecht")
        assert len(result.organizations) == 1
        assert result.organizations[0].name == "Utrecht University"
        assert result.organizations[0].organization_id == "org1"

    @patch("app.utils.ricgraph_utils.autocomplete.utils.database_utils")
    def test_returns_mixed_results(self, mock_db):
        from app.utils.ricgraph_utils.autocomplete import get_autocomplete_suggestions

        mock_db.execute_cypher.return_value = [
            {"id": "p1", "displayName": "John Smith", "type": "person", "bestScore": 100},
            {"id": "o1", "displayName": "Smith Corp", "type": "organization", "bestScore": 50},
        ]
        mock_db.FULLTEXT_INDEX_NAME = "ValueFulltextIndex"

        result = get_autocomplete_suggestions("smith")
        assert len(result.persons) == 1
        assert len(result.organizations) == 1

    @patch("app.utils.ricgraph_utils.autocomplete.utils.database_utils")
    def test_passes_correct_parameters(self, mock_db):
        from app.utils.ricgraph_utils.autocomplete import get_autocomplete_suggestions

        mock_db.execute_cypher.return_value = []
        mock_db.FULLTEXT_INDEX_NAME = "ValueFulltextIndex"

        get_autocomplete_suggestions("henk boer", limit=5)

        call_kwargs = mock_db.execute_cypher.call_args
        assert call_kwargs.kwargs["keywords"] == ["henk", "boer"]
        assert call_kwargs.kwargs["firstKeyword"] == "henk"
        assert call_kwargs.kwargs["cleanQuery"] == "henk boer"
        assert call_kwargs.kwargs["limit"] == 5
        assert "henk*" in call_kwargs.kwargs["luceneQuery"]
        assert "boer*" in call_kwargs.kwargs["luceneQuery"]

    @patch("app.utils.ricgraph_utils.autocomplete.utils.database_utils")
    def test_unknown_type_raises_autocomplete_error(self, mock_db):
        from app.utils.ricgraph_utils.autocomplete import (
            get_autocomplete_suggestions,
            AutocompleteError,
        )

        mock_db.execute_cypher.return_value = [
            {"id": "x1", "displayName": "Unknown Thing", "type": "unknown", "bestScore": 10},
        ]
        mock_db.FULLTEXT_INDEX_NAME = "ValueFulltextIndex"

        with pytest.raises(AutocompleteError, match="Unexpected type"):
            get_autocomplete_suggestions("unknown")
