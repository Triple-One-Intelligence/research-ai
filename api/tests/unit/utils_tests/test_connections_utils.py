"""Tests for connections utility functions."""

from unittest.mock import MagicMock, patch
import pytest

from app.utils.schemas import Person, Organization
from app.utils.schemas.connections import Member
from app.utils.ricgraph_utils.connections import (
    clean_name,
    clean_title,
    parse_year,
    format_people,
    format_organizations,
    format_publications,
    get_connections,
    person_connections,
    organization_connections,
    ConnectionsError,
    InvalidEntityTypeError,
)


# ── clean_name ───────────────────────────────────────────────────────────────

class TestCleanName:
    def test_removes_uuid_suffix(self):
        assert clean_name("Boer, H.#some-uuid") == "Boer, H."

    def test_strips_leading_comma(self):
        assert clean_name(", Boer H.") == "Boer H."

    def test_plain_name_unchanged(self):
        assert clean_name("Henk Boer") == "Henk Boer"

    def test_none_returns_empty(self):
        assert clean_name(None) == ""

    def test_empty_returns_empty(self):
        assert clean_name("") == ""

    def test_strips_whitespace(self):
        assert clean_name("  Boer, H.  ") == "Boer, H."

    def test_leading_comma_and_uuid_combined(self):
        assert clean_name(", Boer H.#abc-123") == "Boer H."

    def test_multiple_hashes_only_splits_first(self):
        assert clean_name("Name#hash1#hash2") == "Name"

    def test_comma_only(self):
        assert clean_name(",") == ""

    def test_hash_only(self):
        assert clean_name("#uuid") == ""


# ── clean_title ──────────────────────────────────────────────────────────────

class TestCleanTitle:
    def test_string_title(self):
        assert clean_title("My Paper") == "My Paper"

    def test_list_title_returns_first(self):
        assert clean_title(["First", "Second"]) == "First"

    def test_empty_list_returns_none(self):
        assert clean_title([]) is None

    def test_none_returns_none(self):
        assert clean_title(None) is None

    def test_empty_string_returns_none(self):
        assert clean_title("  ") is None

    def test_strips_whitespace(self):
        assert clean_title("  My Paper  ") == "My Paper"

    def test_non_string_non_list_returns_none(self):
        assert clean_title(12345) is None

    def test_list_with_single_element(self):
        assert clean_title(["Only One"]) == "Only One"


# ── parse_year ───────────────────────────────────────────────────────────────

class TestParseYear:
    def test_int_passthrough(self):
        assert parse_year(2024) == 2024

    def test_string_number(self):
        assert parse_year("2023") == 2023

    def test_invalid_string_returns_none(self):
        assert parse_year("unknown") is None

    def test_none_returns_none(self):
        assert parse_year(None) is None

    def test_empty_string_returns_none(self):
        assert parse_year("") is None

    def test_whitespace_only_returns_none(self):
        assert parse_year("   ") is None

    def test_float_returns_none(self):
        assert parse_year(20.24) is None

    def test_negative_int_passthrough(self):
        assert parse_year(-1) == -1

    def test_string_with_leading_whitespace(self):
        assert parse_year(" 2024 ") == 2024


# ── format_people ────────────────────────────────────────────────────────────

class TestFormatPeople:
    def test_formats_as_persons(self):
        rows = [{"author_id": "p1", "rawName": "Boer, H.#uuid"}]
        result = format_people(rows)
        assert len(result) == 1
        assert result[0].author_id == "p1"
        assert result[0].name == "Boer, H."

    def test_formats_as_members(self):
        rows = [{"author_id": "p1", "rawName": "Boer, H."}]
        result = format_people(rows, as_members=True)
        assert len(result) == 1
        assert result[0].author_id == "p1"
        assert isinstance(result[0], Member)

    def test_empty_rows(self):
        assert format_people([]) == []

    def test_multiple_rows(self):
        rows = [
            {"author_id": "p1", "rawName": "Alice"},
            {"author_id": "p2", "rawName": "Bob"},
        ]
        result = format_people(rows)
        assert len(result) == 2
        assert all(isinstance(p, Person) for p in result)
        assert result[0].name == "Alice"
        assert result[1].name == "Bob"

    def test_missing_raw_name_uses_clean_name_fallback(self):
        rows = [{"author_id": "p1", "rawName": None}]
        result = format_people(rows)
        assert result[0].name == ""


# ── format_organizations ─────────────────────────────────────────────────────

class TestFormatOrganizations:
    def test_formats_correctly(self):
        rows = [{"organization_id": "o1", "name": "Utrecht University"}]
        result = format_organizations(rows)
        assert len(result) == 1
        assert result[0].organization_id == "o1"
        assert result[0].name == "Utrecht University"

    def test_empty_rows(self):
        assert format_organizations([]) == []

    def test_multiple_orgs(self):
        rows = [
            {"organization_id": "o1", "name": "Org A"},
            {"organization_id": "o2", "name": "Org B"},
        ]
        result = format_organizations(rows)
        assert len(result) == 2
        assert all(isinstance(o, Organization) for o in result)


# ── format_publications ──────────────────────────────────────────────────────

class TestFormatPublications:
    def test_basic_publication(self):
        rows = [{"doi": "10.1/a", "title": "Paper A", "year": "2024", "category": "article"}]
        result = format_publications(rows)
        assert len(result) == 1
        assert result[0].doi == "10.1/a"
        assert result[0].title == "Paper A"
        assert result[0].year == 2024

    def test_deduplicates_by_title(self):
        rows = [
            {"doi": "10.1/a", "title": "Same Paper", "year": "2024", "category": "article"},
            {"doi": "10.1/b", "title": "Same Paper", "year": "2023", "category": "preprint"},
        ]
        result = format_publications(rows)
        assert len(result) == 1
        assert result[0].versions is not None
        assert len(result[0].versions) == 2

    def test_null_title_not_grouped(self):
        rows = [
            {"doi": "10.1/a", "title": None, "year": None, "category": None},
            {"doi": "10.1/b", "title": None, "year": None, "category": None},
        ]
        result = format_publications(rows)
        assert len(result) == 2

    def test_sorted_by_year_descending(self):
        rows = [
            {"doi": "10.1/a", "title": "Old", "year": "2020", "category": None},
            {"doi": "10.1/b", "title": "New", "year": "2024", "category": None},
        ]
        result = format_publications(rows)
        assert result[0].year == 2024
        assert result[1].year == 2020

    def test_case_insensitive_dedup(self):
        """Titles differing only in case should be grouped."""
        rows = [
            {"doi": "10.1/a", "title": "My Paper", "year": "2024", "category": "article"},
            {"doi": "10.1/b", "title": "my paper", "year": "2023", "category": "preprint"},
        ]
        result = format_publications(rows)
        assert len(result) == 1
        assert result[0].versions is not None
        assert len(result[0].versions) == 2

    def test_none_year_sorted_last(self):
        """Publications with year=None should sort after those with years."""
        rows = [
            {"doi": "10.1/a", "title": "No Year", "year": None, "category": None},
            {"doi": "10.1/b", "title": "Has Year", "year": "2020", "category": None},
        ]
        result = format_publications(rows)
        assert result[0].title == "Has Year"
        assert result[1].title == "No Year"

    def test_single_entry_has_no_versions(self):
        rows = [{"doi": "10.1/a", "title": "Solo", "year": "2024", "category": "article"}]
        result = format_publications(rows)
        assert result[0].versions is None

    def test_empty_rows(self):
        assert format_publications([]) == []

    def test_mixed_titled_and_untitled(self):
        rows = [
            {"doi": "10.1/a", "title": "Titled", "year": "2024", "category": "article"},
            {"doi": "10.1/b", "title": None, "year": None, "category": None},
        ]
        result = format_publications(rows)
        assert len(result) == 2


# ── get_connections ──────────────────────────────────────────────────────────

class TestGetConnections:
    def test_invalid_entity_type_raises(self):
        with pytest.raises(InvalidEntityTypeError):
            get_connections("id", "invalid_type")

    def test_invalid_entity_type_raises_value_error(self):
        with pytest.raises(InvalidEntityTypeError, match="must be 'person' or 'organization'"):
            get_connections("id", "unknown_type")

    @patch("app.utils.ricgraph_utils.connections.utils.database_utils")
    def test_person_returns_structure(self, mock_db):
        mock_session = MagicMock()
        mock_session.run.return_value.single.return_value = MagicMock(
            data=lambda: {"rootKey": "root-1"}
        )
        mock_session.run.return_value.data.return_value = []

        mock_db.get_graph.return_value.session.return_value.__enter__ = MagicMock(return_value=mock_session)
        mock_db.get_graph.return_value.session.return_value.__exit__ = MagicMock(return_value=False)

        result = get_connections("p1", "person")
        assert "collaborators" in result
        assert "publications" in result
        assert "organizations" in result
        assert "members" in result

    @patch("app.utils.ricgraph_utils.connections.utils.database_utils")
    def test_organization_returns_structure(self, mock_db):
        mock_session = MagicMock()
        mock_session.run.return_value.data.return_value = []

        mock_db.get_graph.return_value.session.return_value.__enter__ = MagicMock(return_value=mock_session)
        mock_db.get_graph.return_value.session.return_value.__exit__ = MagicMock(return_value=False)

        result = get_connections("o1", "organization")
        assert "collaborators" in result
        assert "publications" in result
        assert "organizations" in result
        assert "members" in result
        assert result["collaborators"] == []

    @patch("app.utils.ricgraph_utils.connections.utils.database_utils")
    def test_db_exception_wrapped_in_connections_error(self, mock_db):
        mock_db.get_graph.side_effect = RuntimeError("driver not initialized")

        with pytest.raises(ConnectionsError, match="Connections query failed"):
            get_connections("p1", "person")

    @patch("app.utils.ricgraph_utils.connections.utils.database_utils")
    def test_org_db_exception_wrapped_in_connections_error(self, mock_db):
        mock_db.get_graph.side_effect = RuntimeError("driver not initialized")

        with pytest.raises(ConnectionsError, match="Connections query failed"):
            get_connections("o1", "organization")


# ── person_connections ───────────────────────────────────────────────────────

class TestPersonConnections:
    @patch("app.utils.ricgraph_utils.connections.utils.database_utils")
    def test_calls_correct_queries(self, mock_db):
        mock_session = MagicMock()
        mock_session.run.return_value.data.return_value = []
        mock_db.get_graph.return_value.session.return_value.__enter__ = MagicMock(return_value=mock_session)
        mock_db.get_graph.return_value.session.return_value.__exit__ = MagicMock(return_value=False)

        result = person_connections("p1", max_publications=10, max_collaborators=5, max_organizations=3)

        assert mock_session.run.call_count == 3
        assert result["members"] == []

    @patch("app.utils.ricgraph_utils.connections.utils.database_utils")
    def test_passes_limits_to_queries(self, mock_db):
        mock_session = MagicMock()
        mock_session.run.return_value.data.return_value = []
        mock_db.get_graph.return_value.session.return_value.__enter__ = MagicMock(return_value=mock_session)
        mock_db.get_graph.return_value.session.return_value.__exit__ = MagicMock(return_value=False)

        person_connections("p1", max_publications=10, max_collaborators=5, max_organizations=3)

        calls = mock_session.run.call_args_list
        # Collaborators call
        assert calls[0].kwargs["limit"] == 5
        # Publications call
        assert calls[1].kwargs["limit"] == 10
        # Organizations call
        assert calls[2].kwargs["limit"] == 3

    @patch("app.utils.ricgraph_utils.connections.utils.database_utils")
    def test_formats_results(self, mock_db):
        mock_session = MagicMock()
        mock_db.get_graph.return_value.session.return_value.__enter__ = MagicMock(return_value=mock_session)
        mock_db.get_graph.return_value.session.return_value.__exit__ = MagicMock(return_value=False)

        mock_session.run.return_value.data.side_effect = [
            [{"author_id": "c1", "rawName": "Collaborator"}],  # collaborators
            [{"doi": "10.1/a", "title": "Paper", "year": "2024", "category": "article"}],  # publications
            [{"organization_id": "o1", "name": "Org"}],  # organizations
        ]

        result = person_connections("p1", max_publications=50, max_collaborators=50, max_organizations=50)

        assert len(result["collaborators"]) == 1
        assert result["collaborators"][0].name == "Collaborator"
        assert len(result["publications"]) == 1
        assert result["publications"][0].doi == "10.1/a"
        assert len(result["organizations"]) == 1
        assert result["organizations"][0].name == "Org"


# ── organization_connections ─────────────────────────────────────────────────

class TestOrganizationConnections:
    @patch("app.utils.ricgraph_utils.connections.utils.database_utils")
    def test_calls_correct_queries(self, mock_db):
        mock_session = MagicMock()
        mock_session.run.return_value.data.return_value = []
        mock_db.get_graph.return_value.session.return_value.__enter__ = MagicMock(return_value=mock_session)
        mock_db.get_graph.return_value.session.return_value.__exit__ = MagicMock(return_value=False)

        result = organization_connections("o1", max_publications=10, max_organizations=5, max_members=3)

        assert mock_session.run.call_count == 3
        assert result["collaborators"] == []

    @patch("app.utils.ricgraph_utils.connections.utils.database_utils")
    def test_members_formatted_as_member_type(self, mock_db):
        mock_session = MagicMock()
        mock_db.get_graph.return_value.session.return_value.__enter__ = MagicMock(return_value=mock_session)
        mock_db.get_graph.return_value.session.return_value.__exit__ = MagicMock(return_value=False)

        mock_session.run.return_value.data.side_effect = [
            [],  # publications
            [],  # organizations
            [{"author_id": "m1", "rawName": "Member Name"}],  # members
        ]

        result = organization_connections("o1", max_publications=50, max_organizations=50, max_members=50)

        assert len(result["members"]) == 1
        assert isinstance(result["members"][0], Member)
        assert result["members"][0].name == "Member Name"
