"""Tests for the connections router and connections_utils."""

from unittest.mock import patch, MagicMock
import pytest
from fastapi.testclient import TestClient

from app.utils.ricgraph_utils.connections_utils import (
    clean_name, clean_title, parse_year,
    format_people, format_organizations, format_publications,
    get_connections, InvalidEntityTypeError, ConnectionsError,
)


# ── Unit tests for helper functions ───────────────────────────────────────────

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

    def test_empty_rows(self):
        assert format_people([]) == []


class TestFormatOrganizations:
    def test_formats_correctly(self):
        rows = [{"organization_id": "o1", "name": "Utrecht University"}]
        result = format_organizations(rows)
        assert len(result) == 1
        assert result[0].organization_id == "o1"
        assert result[0].name == "Utrecht University"


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


# ── Unit tests for get_connections ────────────────────────────────────────────

class TestGetConnections:
    def test_invalid_entity_type_raises(self):
        with pytest.raises(InvalidEntityTypeError):
            get_connections("id", "invalid_type")

    @patch("app.utils.ricgraph_utils.connections_utils.database_utils")
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

    @patch("app.utils.ricgraph_utils.connections_utils.database_utils")
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


# ── API endpoint tests ────────────────────────────────────────────────────────

@pytest.fixture
def client():
    with patch("app.utils.database_utils.database_utils.startup"):
        with patch("app.utils.database_utils.database_utils.shutdown"):
            from app.main import app
            with TestClient(app) as c:
                yield c


class TestConnectionsEndpoint:
    @patch("app.routers.connections.get_connections")
    def test_person_entity(self, mock_gc, client):
        mock_gc.return_value = {
            "collaborators": [], "publications": [],
            "organizations": [], "members": [],
        }
        resp = client.get("/connections/entity", params={
            "entity_id": "person-1", "entity_type": "person",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["entity_id"] == "person-1"
        assert data["entity_type"] == "person"

    @patch("app.routers.connections.get_connections")
    def test_organization_entity(self, mock_gc, client):
        mock_gc.return_value = {
            "collaborators": [], "publications": [],
            "organizations": [], "members": [],
        }
        resp = client.get("/connections/entity", params={
            "entity_id": "org-1", "entity_type": "organization",
        })
        assert resp.status_code == 200
        assert resp.json()["entity_type"] == "organization"

    @patch("app.routers.connections.get_connections")
    def test_invalid_entity_type_returns_400(self, mock_gc, client):
        mock_gc.side_effect = InvalidEntityTypeError("bad type")
        resp = client.get("/connections/entity", params={
            "entity_id": "x", "entity_type": "invalid",
        })
        assert resp.status_code == 400

    @patch("app.routers.connections.get_connections")
    def test_connections_error_returns_500(self, mock_gc, client):
        mock_gc.side_effect = ConnectionsError("db error")
        resp = client.get("/connections/entity", params={
            "entity_id": "x", "entity_type": "person",
        })
        assert resp.status_code == 500

    def test_missing_entity_id(self, client):
        resp = client.get("/connections/entity", params={"entity_type": "person"})
        assert resp.status_code == 422

    def test_missing_entity_type(self, client):
        resp = client.get("/connections/entity", params={"entity_id": "p1"})
        assert resp.status_code == 422

    @patch("app.routers.connections.get_connections")
    def test_limit_params_passed_through(self, mock_gc, client):
        mock_gc.return_value = {
            "collaborators": [], "publications": [],
            "organizations": [], "members": [],
        }
        client.get("/connections/entity", params={
            "entity_id": "p1", "entity_type": "person",
            "max_publications": 10, "max_collaborators": 20,
            "max_organizations": 30, "max_members": 40,
        })
        call_kwargs = mock_gc.call_args.kwargs
        assert call_kwargs["max_publications"] == 10
        assert call_kwargs["max_collaborators"] == 20
        assert call_kwargs["max_organizations"] == 30
        assert call_kwargs["max_members"] == 40

    def test_limit_validation_too_high(self, client):
        resp = client.get("/connections/entity", params={
            "entity_id": "p1", "entity_type": "person",
            "max_publications": 999,
        })
        assert resp.status_code == 422

    def test_limit_validation_too_low(self, client):
        resp = client.get("/connections/entity", params={
            "entity_id": "p1", "entity_type": "person",
            "max_publications": 0,
        })
        assert resp.status_code == 422

    @patch("app.routers.connections.get_connections")
    def test_person_collaborators_endpoint_passes_limit(self, mock_gc, client):
        mock_gc.return_value = {
            "collaborators": [{"author_id": "p2", "name": "Example Coauthor"}],
            "publications": [],
            "organizations": [],
            "members": [],
        }
        resp = client.get("/connections/collaborators", params={
            "entity_id": "person-1",
            "entity_type": "person",
            "max_collaborators": 10,
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["entity_id"] == "person-1"
        assert data["entity_type"] == "person"
        assert data["collaborators"] == [{"author_id": "p2", "name": "Example Coauthor"}]

        call_kwargs = mock_gc.call_args.kwargs
        assert call_kwargs["max_collaborators"] == 10

    @patch("app.routers.connections.get_connections")
    def test_organization_members_endpoint_passes_limit(self, mock_gc, client):
        mock_gc.return_value = {
            "collaborators": [],
            "publications": [],
            "organizations": [],
            "members": [{"author_id": "p1", "name": "Member Example"}],
        }
        resp = client.get("/connections/members", params={
            "entity_id": "org-1",
            "entity_type": "organization",
            "max_members": 5,
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["entity_id"] == "org-1"
        assert data["entity_type"] == "organization"
        assert data["members"] == [{"author_id": "p1", "name": "Member Example"}]

        call_kwargs = mock_gc.call_args.kwargs
        assert call_kwargs["max_members"] == 5

    @patch("app.routers.connections.get_connections")
    def test_person_publications_endpoint_passes_limit(self, mock_gc, client):
        mock_gc.return_value = {
            "collaborators": [],
            "publications": [{"doi": "10.1/a", "title": "Paper A", "year": 2024, "category": "article"}],
            "organizations": [],
            "members": [],
        }
        resp = client.get("/connections/publications", params={
            "entity_id": "person-1",
            "entity_type": "person",
            "max_publications": 7,
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["entity_id"] == "person-1"
        assert data["entity_type"] == "person"
        assert data["publications"][0]["doi"] == "10.1/a"

        call_kwargs = mock_gc.call_args.kwargs
        assert call_kwargs["max_publications"] == 7

    @patch("app.routers.connections.get_connections")
    def test_person_organizations_endpoint_passes_limit(self, mock_gc, client):
        mock_gc.return_value = {
            "collaborators": [],
            "publications": [],
            "organizations": [{"organization_id": "org-2", "name": "Example Org"}],
            "members": [],
        }
        resp = client.get("/connections/organizations", params={
            "entity_id": "person-1",
            "entity_type": "person",
            "max_organizations": 12,
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["entity_id"] == "person-1"
        assert data["entity_type"] == "person"
        assert data["organizations"] == [{"organization_id": "org-2", "name": "Example Org"}]

        call_kwargs = mock_gc.call_args.kwargs
        assert call_kwargs["max_organizations"] == 12
