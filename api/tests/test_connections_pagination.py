import pytest

from app.utils.schemas import Organization, Person, Publication
from app.utils.ricgraph_utils.connections import (
    InvalidCursorError,
    decode_cursor,
    decode_cursor_pair,
    encode_cursor,
    extract_next_cursor,
    extract_organization_next_cursor,
    extract_people_next_cursor,
    extract_publication_next_cursor,
    publication_sort_key,
    trim_page,
)


def test_encode_decode_cursor_roundtrip():
    payload = {"name": "alpha", "author_id": "a-1"}
    cursor = encode_cursor(payload)
    assert decode_cursor(cursor, ("name", "author_id")) == payload


@pytest.mark.parametrize("cursor", ["%%%not-base64%%%", encode_cursor(["bad", "payload"])])
def test_decode_cursor_invalid_payload_raises(cursor):
    with pytest.raises(InvalidCursorError):
        decode_cursor(cursor, ("name",))


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"name": "", "author_id": "a-1"},
        {"name": "alpha", "author_id": ""},
        {"name": 42, "author_id": "a-1"},
    ],
)
def test_decode_cursor_required_keys_validation(payload):
    with pytest.raises(InvalidCursorError):
        decode_cursor(encode_cursor(payload), ("name", "author_id"))


def test_decode_cursor_none_returns_empty():
    assert decode_cursor(None, ("name",)) == {}


def test_decode_cursor_pair_no_cursor_returns_none_pair():
    assert decode_cursor_pair(None, "name", "author_id") == (None, None)


def test_decode_cursor_pair_returns_values():
    cursor = encode_cursor({"sort_key": "title:abc", "doi": "10.1/a"})
    assert decode_cursor_pair(cursor, "sort_key", "doi") == ("title:abc", "10.1/a")


def test_decode_cursor_pair_invalid_cursor_raises():
    with pytest.raises(InvalidCursorError):
        decode_cursor_pair("not-valid", "name", "author_id")


def test_publication_sort_key_prefers_title():
    assert publication_sort_key("  A Title  ", "10.1/a") == "title:a title"


def test_publication_sort_key_falls_back_to_doi():
    assert publication_sort_key("   ", "10.1/a") == "doi:10.1/a"


def test_extract_next_cursor_returns_none_when_no_extra_item():
    items = [Person(author_id="a1", name="One", sort_name="one")]
    cursor = extract_next_cursor(
        items,
        1,
        id_attr="author_id",
        name_attr="sort_name",
        encode=lambda name, item_id: f"{name}:{item_id}",
    )
    assert cursor is None


def test_extract_next_cursor_returns_none_when_limit_invalid():
    items = [Person(author_id="a1", name="One", sort_name="one")]
    assert (
        extract_next_cursor(
            items,
            0,
            id_attr="author_id",
            name_attr="sort_name",
            encode=lambda name, item_id: f"{name}:{item_id}",
        )
        is None
    )


def test_extract_next_cursor_returns_none_when_id_missing():
    class Row:
        def __init__(self, sort_name):
            self.sort_name = sort_name

    items = [Row("first"), Row("second")]
    assert (
        extract_next_cursor(
            items,
            1,
            id_attr="author_id",
            name_attr="sort_name",
            encode=lambda name, item_id: f"{name}:{item_id}",
        )
        is None
    )


def test_extract_next_cursor_id_only_mode():
    items = [
        Publication(doi="10.1/a", title="A"),
        Publication(doi="10.1/b", title="B"),
    ]
    cursor = extract_next_cursor(
        items,
        1,
        id_attr="doi",
        encode=lambda item_id: f"id:{item_id}",
    )
    assert cursor == "id:10.1/a"


def test_extract_next_cursor_uses_fallback_name_attr():
    items = [
        Person(author_id="a1", name="Name One"),
        Person(author_id="a2", name="Name Two"),
    ]
    cursor = extract_next_cursor(
        items,
        1,
        id_attr="author_id",
        name_attr="sort_name",
        fallback_name_attr="name",
        encode=lambda name, item_id: f"{name}:{item_id}",
    )
    assert cursor == "Name One:a1"


def test_extract_people_next_cursor():
    people = [
        Person(author_id="a1", name="A One", sort_name="one,a"),
        Person(author_id="a2", name="A Two", sort_name="two,a"),
    ]
    cursor = extract_people_next_cursor(people, 1)
    assert decode_cursor(cursor, ("name", "author_id")) == {"name": "one,a", "author_id": "a1"}


def test_extract_organization_next_cursor():
    organizations = [
        Organization(organization_id="o1", name="Org One"),
        Organization(organization_id="o2", name="Org Two"),
    ]
    cursor = extract_organization_next_cursor(organizations, 1)
    assert decode_cursor(cursor, ("name", "organization_id")) == {
        "name": "org one",
        "organization_id": "o1",
    }


def test_extract_publication_next_cursor():
    publications = [
        Publication(doi="10.1/a", title="Alpha Title"),
        Publication(doi="10.1/b", title="Beta Title"),
    ]
    cursor = extract_publication_next_cursor(publications, 1)
    assert decode_cursor(cursor, ("sort_key", "doi")) == {
        "sort_key": "title:alpha title",
        "doi": "10.1/a",
    }


def test_extract_publication_next_cursor_uses_doi_sort_key_for_empty_title():
    publications = [
        Publication(doi="10.1/a", title=None),
        Publication(doi="10.1/b", title="Has Title"),
    ]
    cursor = extract_publication_next_cursor(publications, 1)
    assert decode_cursor(cursor, ("sort_key", "doi")) == {
        "sort_key": "doi:10.1/a",
        "doi": "10.1/a",
    }


def test_extract_organization_next_cursor_blank_name_returns_none():
    organizations = [
        Organization(organization_id="o1", name=""),
        Organization(organization_id="o2", name="Org Two"),
    ]
    assert extract_organization_next_cursor(organizations, 1) is None


def test_extract_next_cursor_blank_name_and_fallback_returns_none():
    items = [
        Person(author_id="a1", name="   ", sort_name=""),
        Person(author_id="a2", name="Two", sort_name="two"),
    ]
    cursor = extract_next_cursor(
        items,
        1,
        id_attr="author_id",
        name_attr="sort_name",
        fallback_name_attr="name",
        encode=lambda name, item_id: f"{name}:{item_id}",
    )
    assert cursor is None


def test_trim_page_behaviors():
    assert trim_page([1, 2, 3], 2) == [1, 2]
    assert trim_page([1, 2, 3], 0) == []
    assert trim_page([1, 2, 3], -1) == []
