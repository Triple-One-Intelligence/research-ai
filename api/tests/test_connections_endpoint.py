"""Tests for the connections router and connections package."""

from unittest.mock import patch, MagicMock
import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.utils.ricgraph_utils.connections import (
    clean_name, clean_title, parse_year,
    format_people, format_organizations, format_publications,
    get_connections, InvalidEntityTypeError, InvalidCursorError, ConnectionsError,
    encode_cursor,
)
from app.utils.schemas import Member, Organization, Person, Publication


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

    def test_preserves_rows_with_same_title(self):
        rows = [
            {"doi": "10.1/a", "title": "Same Paper", "year": "2024", "category": "article"},
            {"doi": "10.1/b", "title": "Same Paper", "year": "2023", "category": "preprint"},
        ]
        result = format_publications(rows)
        assert len(result) == 2
        assert result[0].doi == "10.1/a"
        assert result[1].doi == "10.1/b"

    def test_null_title_not_grouped(self):
        rows = [
            {"doi": "10.1/a", "title": None, "year": None, "category": None},
            {"doi": "10.1/b", "title": None, "year": None, "category": None},
        ]
        result = format_publications(rows)
        assert len(result) == 2

    def test_preserves_query_order(self):
        rows = [
            {"doi": "10.1/a", "title": "Old", "year": "2020", "category": None},
            {"doi": "10.1/b", "title": "New", "year": "2024", "category": None},
        ]
        result = format_publications(rows)
        assert result[0].year == 2020
        assert result[1].year == 2024


# ── Unit tests for get_connections ────────────────────────────────────────────

class TestGetConnections:
    def test_invalid_entity_type_raises(self):
        with pytest.raises(InvalidEntityTypeError):
            get_connections("id", "invalid_type")

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
        assert resp.json()["detail"] == "Connections query failed."

    @patch("app.routers.connections.get_connections")
    def test_invalid_cursor_returns_400(self, mock_gc, client):
        mock_gc.side_effect = InvalidCursorError("bad cursor")
        resp = client.get("/connections/entity", params={
            "entity_id": "x", "entity_type": "person",
        })
        assert resp.status_code == 400
        assert "bad cursor" in resp.json()["detail"]

    @patch("app.routers.connections.get_connections")
    def test_http_exception_passthrough(self, mock_gc, client):
        mock_gc.side_effect = HTTPException(status_code=409, detail="conflict")
        resp = client.get("/connections/entity", params={
            "entity_id": "x", "entity_type": "person",
        })
        assert resp.status_code == 409
        assert resp.json()["detail"] == "conflict"

    @patch("app.routers.connections.get_connections")
    def test_unexpected_exception_returns_500(self, mock_gc, client):
        mock_gc.side_effect = RuntimeError("boom")
        resp = client.get("/connections/entity", params={
            "entity_id": "x", "entity_type": "person",
        })
        assert resp.status_code == 500
        assert resp.json()["detail"] == "Connections query failed."

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
        assert call_kwargs["max_publications"] == 11
        assert call_kwargs["max_collaborators"] == 21
        assert call_kwargs["max_organizations"] == 31
        assert call_kwargs["max_members"] == 41

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

    @pytest.mark.parametrize("param_name", [
        "max_collaborators",
        "max_organizations",
        "max_members",
    ])
    def test_entity_limit_validation_too_high_for_other_limits(self, client, param_name):
        resp = client.get("/connections/entity", params={
            "entity_id": "p1",
            "entity_type": "person",
            param_name: 999,
        })
        assert resp.status_code == 422

    @pytest.mark.parametrize("param_name", [
        "max_collaborators",
        "max_organizations",
        "max_members",
    ])
    def test_entity_limit_validation_too_low_for_other_limits(self, client, param_name):
        resp = client.get("/connections/entity", params={
            "entity_id": "p1",
            "entity_type": "person",
            param_name: 0,
        })
        assert resp.status_code == 422

    @patch("app.routers.connections.get_connections")
    def test_entity_connections_trims_and_sets_cursors(self, mock_gc, client):
        mock_gc.return_value = {
            "collaborators": [
                Person(author_id="a1", name="A One", sort_name="one,a"),
                Person(author_id="a2", name="A Two", sort_name="two,a"),
            ],
            "publications": [
                Publication(doi="10.1/a", title="Paper A", year=2023, category="article"),
                Publication(doi="10.1/b", title="Paper B", year=2024, category="article"),
            ],
            "organizations": [
                Organization(organization_id="o1", name="Org One"),
                Organization(organization_id="o2", name="Org Two"),
            ],
            "members": [
                Member(author_id="m1", name="Member One", sort_name="member,one"),
                Member(author_id="m2", name="Member Two", sort_name="member,two"),
            ],
        }
        resp = client.get("/connections/entity", params={
            "entity_id": "root-1",
            "entity_type": "person",
            "max_collaborators": 1,
            "max_publications": 1,
            "max_organizations": 1,
            "max_members": 1,
        })
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["collaborators"]) == 1
        assert len(data["publications"]) == 1
        assert len(data["organizations"]) == 1
        assert len(data["members"]) == 1
        assert data["collaborators_cursor"] is not None
        assert data["publications_cursor"] is not None
        assert data["organizations_cursor"] is not None
        assert data["members_cursor"] is not None

    @patch("app.routers.connections.get_collaborators_list")
    def test_person_collaborators_endpoint_passes_limit(self, mock_gc, client):
        mock_gc.return_value = [
            Person(author_id="p2", name="Example Coauthor", sort_name="coauthor,example"),
            Person(author_id="p3", name="Second Coauthor", sort_name="coauthor,second"),
        ]
        resp = client.get("/connections/collaborators", params={
            "entity_id": "person-1",
            "entity_type": "person",
            "limit": 1,
            "cursor": "cur-1",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["entity_id"] == "person-1"
        assert data["entity_type"] == "person"
        assert data["collaborators"] == [{"author_id": "p2", "name": "Example Coauthor"}]
        assert data["cursor"] == encode_cursor({"name": "coauthor,example", "author_id": "p2"})

        call_kwargs = mock_gc.call_args.kwargs
        assert call_kwargs["max_collaborators"] == 2
        assert call_kwargs["cursor"] == "cur-1"

    @patch("app.routers.connections.get_members_list")
    def test_organization_members_endpoint_passes_limit(self, mock_gc, client):
        mock_gc.return_value = [
            Member(author_id="p1", name="Member Example", sort_name="member,example"),
            Member(author_id="p2", name="Member Example 2", sort_name="member,example2"),
        ]
        resp = client.get("/connections/members", params={
            "entity_id": "org-1",
            "entity_type": "organization",
            "limit": 1,
            "cursor": "cur-2",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["entity_id"] == "org-1"
        assert data["entity_type"] == "organization"
        assert data["members"] == [{"author_id": "p1", "name": "Member Example"}]
        assert data["cursor"] == encode_cursor({"name": "member,example", "author_id": "p1"})

        call_kwargs = mock_gc.call_args.kwargs
        assert call_kwargs["max_members"] == 2
        assert call_kwargs["cursor"] == "cur-2"

    @patch("app.routers.connections.get_publications_list")
    def test_person_publications_endpoint_passes_limit(self, mock_gc, client):
        mock_gc.return_value = [
            Publication(doi="10.1/a", title="Paper A", year=2024, category="article"),
            Publication(doi="10.1/b", title="Paper B", year=2025, category="article"),
        ]
        resp = client.get("/connections/publications", params={
            "entity_id": "person-1",
            "entity_type": "person",
            "limit": 1,
            "cursor": "cur-3",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["entity_id"] == "person-1"
        assert data["entity_type"] == "person"
        assert data["publications"][0]["doi"] == "10.1/a"
        assert data["cursor"] == encode_cursor({"sort_key": "title:paper a", "doi": "10.1/a"})

        call_kwargs = mock_gc.call_args.kwargs
        assert call_kwargs["max_publications"] == 2
        assert call_kwargs["cursor"] == "cur-3"

    @patch("app.routers.connections.get_organizations_list")
    def test_person_organizations_endpoint_passes_limit(self, mock_gc, client):
        mock_gc.return_value = [
            Organization(organization_id="org-2", name="Example Org"),
            Organization(organization_id="org-3", name="Another Org"),
        ]
        resp = client.get("/connections/organizations", params={
            "entity_id": "person-1",
            "entity_type": "person",
            "limit": 1,
            "cursor": "cur-4",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["entity_id"] == "person-1"
        assert data["entity_type"] == "person"
        assert data["organizations"] == [{"organization_id": "org-2", "name": "Example Org"}]
        assert data["cursor"] == encode_cursor({"name": "example org", "organization_id": "org-2"})

        call_kwargs = mock_gc.call_args.kwargs
        assert call_kwargs["max_organizations"] == 2
        assert call_kwargs["cursor"] == "cur-4"

    @pytest.mark.parametrize("endpoint", [
        "/connections/collaborators",
        "/connections/publications",
        "/connections/organizations",
        "/connections/members",
    ])
    def test_list_endpoint_limit_validation_too_high(self, client, endpoint):
        resp = client.get(endpoint, params={
            "entity_id": "e1",
            "entity_type": "person",
            "limit": 999,
        })
        assert resp.status_code == 422

    @pytest.mark.parametrize("endpoint", [
        "/connections/collaborators",
        "/connections/publications",
        "/connections/organizations",
        "/connections/members",
    ])
    def test_list_endpoint_limit_validation_too_low(self, client, endpoint):
        resp = client.get(endpoint, params={
            "entity_id": "e1",
            "entity_type": "person",
            "limit": 0,
        })
        assert resp.status_code == 422

    @pytest.mark.parametrize(
        "endpoint,patch_target,error",
        [
            ("/connections/collaborators", "app.routers.connections.get_collaborators_list", InvalidEntityTypeError("bad type")),
            ("/connections/publications", "app.routers.connections.get_publications_list", InvalidCursorError("bad cursor")),
            ("/connections/organizations", "app.routers.connections.get_organizations_list", ConnectionsError("db")),
            ("/connections/members", "app.routers.connections.get_members_list", RuntimeError("boom")),
        ],
    )
    def test_list_endpoints_exception_mapping(self, client, endpoint, patch_target, error):
        with patch(patch_target) as mock_call:
            mock_call.side_effect = error
            resp = client.get(endpoint, params={
                "entity_id": "e1",
                "entity_type": "person",
                "limit": 1,
            })

        if isinstance(error, (InvalidEntityTypeError, InvalidCursorError)):
            assert resp.status_code == 400
        else:
            assert resp.status_code == 500

    @pytest.mark.parametrize(
        "endpoint,patch_target",
        [
            ("/connections/collaborators", "app.routers.connections.get_collaborators_list"),
            ("/connections/publications", "app.routers.connections.get_publications_list"),
            ("/connections/organizations", "app.routers.connections.get_organizations_list"),
            ("/connections/members", "app.routers.connections.get_members_list"),
        ],
    )
    @pytest.mark.parametrize(
        "error,expected_status",
        [
            (InvalidEntityTypeError("bad type"), 400),
            (InvalidCursorError("bad cursor"), 400),
            (ConnectionsError("db fail"), 500),
            (RuntimeError("boom"), 500),
            (HTTPException(status_code=418, detail="teapot"), 418),
        ],
    )
    def test_list_endpoints_full_exception_matrix(
        self,
        client,
        endpoint,
        patch_target,
        error,
        expected_status,
    ):
        with patch(patch_target) as mock_call:
            mock_call.side_effect = error
            resp = client.get(endpoint, params={
                "entity_id": "e1",
                "entity_type": "person",
                "limit": 1,
            })

        assert resp.status_code == expected_status
