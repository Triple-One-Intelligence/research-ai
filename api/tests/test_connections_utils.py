from unittest.mock import MagicMock, patch

import pytest

from app.utils.ricgraph_utils.connections import (
    ConnectionsError,
    InvalidEntityTypeError,
    get_collaborators,
    get_connections,
    get_members,
    get_organizations,
    get_publications,
    organization_connections,
    person_connections,
    run_query,
    run_type_query,
)


@patch("app.utils.ricgraph_utils.connections.utils.database_utils.execute_cypher")
def test_run_query_success(mock_execute_cypher):
    mock_execute_cypher.return_value = [{"id": 1}]
    assert run_query("MATCH (n) RETURN n") == [{"id": 1}]


@patch("app.utils.ricgraph_utils.connections.utils.database_utils.execute_cypher")
def test_run_query_wraps_exceptions(mock_execute_cypher):
    mock_execute_cypher.side_effect = RuntimeError("db down")
    with pytest.raises(ConnectionsError):
        run_query("MATCH (n) RETURN n")


@patch("app.utils.ricgraph_utils.connections.utils.run_query")
def test_run_type_query_dispatches_person(mock_run_query):
    mock_run_query.return_value = [{"ok": True}]
    result = run_type_query(
        "person",
        person_query="PERSON_QUERY",
        person_params={"a": 1},
        organization_query="ORG_QUERY",
        organization_params={"b": 2},
    )
    assert result == [{"ok": True}]
    mock_run_query.assert_called_once_with("PERSON_QUERY", session=None, a=1)


@patch("app.utils.ricgraph_utils.connections.utils.run_query")
def test_run_type_query_dispatches_organization(mock_run_query):
    mock_run_query.return_value = [{"ok": True}]
    result = run_type_query(
        "organization",
        person_query="PERSON_QUERY",
        person_params={"a": 1},
        organization_query="ORG_QUERY",
        organization_params={"b": 2},
    )
    assert result == [{"ok": True}]
    mock_run_query.assert_called_once_with("ORG_QUERY", session=None, b=2)


def test_run_type_query_invalid_type_raises():
    with pytest.raises(InvalidEntityTypeError):
        run_type_query(
            "team",
            person_query="PERSON_QUERY",
            person_params={},
            organization_query="ORG_QUERY",
            organization_params={},
        )


def test_get_collaborators_returns_empty_for_organization():
    assert get_collaborators("org-1", "organization", 10) == []


def test_get_members_returns_empty_for_person():
    assert get_members("person-1", "person", 10) == []


@patch("app.utils.ricgraph_utils.connections.utils.format_people")
@patch("app.utils.ricgraph_utils.connections.utils.run_query")
@patch("app.utils.ricgraph_utils.connections.utils.decode_cursor_pair")
def test_get_collaborators_decodes_cursor_and_maps_params(
    mock_decode_cursor_pair,
    mock_run_query,
    mock_format_people,
):
    mock_decode_cursor_pair.return_value = ("name,a", "a-1")
    mock_run_query.return_value = [{"author_id": "a-1", "rawName": "A Name"}]
    mock_format_people.return_value = ["formatted"]

    result = get_collaborators("p-1", "person", 5, cursor="cur")
    assert result == ["formatted"]
    mock_decode_cursor_pair.assert_called_once_with("cur", "name", "author_id")
    mock_run_query.assert_called_once()
    kwargs = mock_run_query.call_args.kwargs
    assert kwargs["rootValue"] == "p-1"
    assert kwargs["limit"] == 5
    assert kwargs["cursorName"] == "name,a"
    assert kwargs["cursorAuthorId"] == "a-1"


@patch("app.utils.ricgraph_utils.connections.utils.format_publications")
@patch("app.utils.ricgraph_utils.connections.utils.run_type_query")
@patch("app.utils.ricgraph_utils.connections.utils.decode_cursor_pair")
def test_get_publications_person_params(
    mock_decode_cursor_pair,
    mock_run_type_query,
    mock_format_publications,
):
    mock_decode_cursor_pair.return_value = ("title:abc", "10.1/a")
    mock_run_type_query.return_value = [{"doi": "10.1/a"}]
    mock_format_publications.return_value = ["pubs"]

    result = get_publications("p-1", "person", 3, cursor="cur")
    assert result == ["pubs"]
    kwargs = mock_run_type_query.call_args.kwargs
    assert kwargs["person_params"]["rootValue"] == "p-1"
    assert kwargs["organization_params"]["entityId"] == "p-1"
    assert kwargs["person_params"]["cursorKey"] == "title:abc"
    assert kwargs["person_params"]["cursorDoi"] == "10.1/a"


@patch("app.utils.ricgraph_utils.connections.utils.format_publications")
@patch("app.utils.ricgraph_utils.connections.utils.run_type_query")
@patch("app.utils.ricgraph_utils.connections.utils.decode_cursor_pair")
def test_get_publications_organization_entity_type(
    mock_decode_cursor_pair,
    mock_run_type_query,
    mock_format_publications,
):
    mock_decode_cursor_pair.return_value = (None, None)
    mock_run_type_query.return_value = [{"doi": "10.1/z"}]
    mock_format_publications.return_value = ["pubs"]

    result = get_publications("o-1", "organization", 7, cursor=None)
    assert result == ["pubs"]
    assert mock_run_type_query.call_args.args[0] == "organization"
    kwargs = mock_run_type_query.call_args.kwargs
    assert kwargs["organization_params"]["entityId"] == "o-1"
    assert kwargs["organization_params"]["limit"] == 7


@patch("app.utils.ricgraph_utils.connections.utils.format_organizations")
@patch("app.utils.ricgraph_utils.connections.utils.run_type_query")
@patch("app.utils.ricgraph_utils.connections.utils.decode_cursor_pair")
def test_get_organizations_person_and_org_param_shapes(
    mock_decode_cursor_pair,
    mock_run_type_query,
    mock_format_organizations,
):
    mock_decode_cursor_pair.return_value = ("org name", "org-1")
    mock_run_type_query.return_value = [{"organization_id": "org-1", "name": "Org"}]
    mock_format_organizations.return_value = ["orgs"]

    result = get_organizations("p-1", "person", 2, cursor="cur")
    assert result == ["orgs"]
    kwargs = mock_run_type_query.call_args.kwargs
    assert kwargs["person_params"]["rootValue"] == "p-1"
    assert kwargs["organization_params"]["entityId"] == "p-1"
    assert kwargs["person_params"]["cursorName"] == "org name"
    assert kwargs["person_params"]["cursorOrganizationId"] == "org-1"


@patch("app.utils.ricgraph_utils.connections.utils.format_organizations")
@patch("app.utils.ricgraph_utils.connections.utils.run_type_query")
@patch("app.utils.ricgraph_utils.connections.utils.decode_cursor_pair")
def test_get_organizations_organization_entity_type(
    mock_decode_cursor_pair,
    mock_run_type_query,
    mock_format_organizations,
):
    mock_decode_cursor_pair.return_value = (None, None)
    mock_run_type_query.return_value = [{"organization_id": "o-1", "name": "Org"}]
    mock_format_organizations.return_value = ["orgs"]

    result = get_organizations("o-1", "organization", 6, cursor=None)
    assert result == ["orgs"]
    assert mock_run_type_query.call_args.args[0] == "organization"
    kwargs = mock_run_type_query.call_args.kwargs
    assert kwargs["organization_params"]["entityId"] == "o-1"
    assert kwargs["organization_params"]["limit"] == 6


@patch("app.utils.ricgraph_utils.connections.utils.format_people")
@patch("app.utils.ricgraph_utils.connections.utils.run_query")
@patch("app.utils.ricgraph_utils.connections.utils.decode_cursor_pair")
def test_get_members_decodes_cursor_and_maps_params(
    mock_decode_cursor_pair,
    mock_run_query,
    mock_format_people,
):
    mock_decode_cursor_pair.return_value = ("member,a", "a-1")
    mock_run_query.return_value = [{"author_id": "a-1", "rawName": "A Name"}]
    mock_format_people.return_value = ["members"]

    result = get_members("org-1", "organization", 4, cursor="cur")
    assert result == ["members"]
    kwargs = mock_run_query.call_args.kwargs
    assert kwargs["entityId"] == "org-1"
    assert kwargs["limit"] == 4
    assert kwargs["cursorName"] == "member,a"
    assert kwargs["cursorAuthorId"] == "a-1"


@patch("app.utils.ricgraph_utils.connections.utils.database_utils.get_graph")
@patch("app.utils.ricgraph_utils.connections.utils.get_collaborators")
@patch("app.utils.ricgraph_utils.connections.utils.get_publications")
@patch("app.utils.ricgraph_utils.connections.utils.get_organizations")
def test_person_connections_assembled_shape(
    mock_get_organizations,
    mock_get_publications,
    mock_get_collaborators,
    mock_get_graph,
):
    mock_session = MagicMock()
    mock_get_graph.return_value.session.return_value.__enter__.return_value = mock_session
    mock_get_graph.return_value.session.return_value.__exit__.return_value = None

    mock_get_collaborators.return_value = ["c"]
    mock_get_publications.return_value = ["p"]
    mock_get_organizations.return_value = ["o"]
    payload = person_connections("p-1", 10, 20, 30)
    assert payload == {
        "collaborators": ["c"],
        "publications": ["p"],
        "organizations": ["o"],
        "members": [],
    }
    mock_get_collaborators.assert_called_once_with("p-1", "person", 20, session=mock_session)
    mock_get_publications.assert_called_once_with("p-1", "person", 10, session=mock_session)
    mock_get_organizations.assert_called_once_with("p-1", "person", 30, session=mock_session)


@patch("app.utils.ricgraph_utils.connections.utils.get_publications")
@patch("app.utils.ricgraph_utils.connections.utils.get_organizations")
@patch("app.utils.ricgraph_utils.connections.utils.get_members")
def test_organization_connections_assembled_shape(
    mock_get_members,
    mock_get_organizations,
    mock_get_publications,
):
    mock_get_publications.return_value = ["p"]
    mock_get_organizations.return_value = ["o"]
    mock_get_members.return_value = ["m"]
    payload = organization_connections("o-1", 10, 20, 30)
    assert payload == {
        "collaborators": [],
        "publications": ["p"],
        "organizations": ["o"],
        "members": ["m"],
    }


@patch("app.utils.ricgraph_utils.connections.utils.person_connections")
def test_get_connections_dispatches_person(mock_person_connections):
    mock_person_connections.return_value = {"collaborators": [], "publications": [], "organizations": [], "members": []}
    get_connections("p-1", "person", 1, 2, 3, 4)
    mock_person_connections.assert_called_once_with("p-1", 1, 2, 3)


@patch("app.utils.ricgraph_utils.connections.utils.organization_connections")
def test_get_connections_dispatches_organization(mock_organization_connections):
    mock_organization_connections.return_value = {
        "collaborators": [],
        "publications": [],
        "organizations": [],
        "members": [],
    }
    get_connections("o-1", "organization", 1, 2, 3, 4)
    mock_organization_connections.assert_called_once_with("o-1", 1, 3, 4)


def test_get_connections_invalid_type_raises():
    with pytest.raises(InvalidEntityTypeError):
        get_connections("x-1", "team")
