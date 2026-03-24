from app.utils.ricgraph_utils import connections


def test_connections_all_exports_have_attributes():
    for symbol in connections.__all__:
        assert hasattr(connections, symbol), f"Missing exported symbol: {symbol}"


def test_connections_all_contains_core_symbols():
    expected = {
        "get_connections",
        "get_collaborators",
        "get_publications",
        "get_organizations",
        "get_members",
        "encode_cursor",
        "decode_cursor",
        "validate_entity_type",
        "ConnectionsError",
        "InvalidEntityTypeError",
        "InvalidCursorError",
    }
    assert expected.issubset(set(connections.__all__))
