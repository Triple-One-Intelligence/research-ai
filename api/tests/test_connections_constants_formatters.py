import pytest

from app.utils.ricgraph_utils.connections import (
    InvalidEntityTypeError,
    clean_name,
    clean_title,
    format_organizations,
    format_people,
    format_publications,
    normalize_versions,
    parse_year,
    validate_entity_type,
)


@pytest.mark.parametrize("entity_type", ["person", "organization"])
def test_validate_entity_type_accepts_supported_values(entity_type):
    validate_entity_type(entity_type)


@pytest.mark.parametrize("entity_type", ["Person", " organization", "team", ""])
def test_validate_entity_type_rejects_invalid_values(entity_type):
    with pytest.raises(InvalidEntityTypeError):
        validate_entity_type(entity_type)


def test_clean_name_handles_hash_comma_and_empty():
    assert clean_name("Doe, J.#uuid") == "Doe, J."
    assert clean_name(", Doe, J.") == "Doe, J."
    assert clean_name("   ") == ""
    assert clean_name(None) == ""


def test_clean_title_edge_cases():
    assert clean_title(None) is None
    assert clean_title(["A", "B"]) == "A"
    assert clean_title([]) is None
    assert clean_title("   ") is None
    assert clean_title(123) is None
    assert clean_title(["  A title  "]) == "A title"
    assert clean_title([123, "ignored"]) is None


def test_parse_year_branches():
    assert parse_year(2024) == 2024
    assert parse_year(" 2023 ") == 2023
    assert parse_year("invalid") is None
    assert parse_year(True) is None
    assert parse_year(False) is None
    assert parse_year(None) is None


def test_normalize_versions_non_list_returns_none():
    assert normalize_versions(None) is None
    assert normalize_versions("bad") is None


def test_normalize_versions_filters_and_parses_entries():
    versions = normalize_versions(
        [
            {"doi": "10.1/a", "year": "2024", "category": "article"},
            {"doi": "10.1/b", "year": "unknown", "category": "preprint"},
            "skip-me",
        ]
    )
    assert versions == [
        {"doi": "10.1/a", "year": 2024, "category": "article"},
        {"doi": "10.1/b", "year": None, "category": "preprint"},
    ]


def test_format_people_preserves_sort_name_only_when_string():
    people = format_people(
        [
            {"author_id": "a1", "rawName": "Doe, J.", "sort_name": "doe,j"},
            {"author_id": "a2", "rawName": "Smith, A.", "sort_name": 123},
        ]
    )
    assert people[0].sort_name == "doe,j"
    assert people[1].sort_name is None


def test_format_people_as_members():
    members = format_people([{"author_id": "m1", "rawName": "Member, One"}], as_members=True)
    assert members[0].author_id == "m1"
    assert members[0].name == "Member, One"


def test_format_people_missing_author_id_raises():
    with pytest.raises(KeyError):
        format_people([{"rawName": "No Id"}])


def test_format_organizations_missing_key_raises():
    with pytest.raises(KeyError):
        format_organizations([{"name": "Missing id"}])


def test_format_publications_versions_and_required_key():
    publications = format_publications(
        [
            {
                "doi": "10.1/a",
                "title": ["Publication title", "ignored"],
                "year": "2022",
                "category": "article",
                "versions": [{"doi": "10.1/a.v1", "year": "2021", "category": "preprint"}],
            }
        ]
    )
    assert publications[0].title == "Publication title"
    assert publications[0].year == 2022
    assert publications[0].versions == [
        {"doi": "10.1/a.v1", "year": 2021, "category": "preprint"}
    ]

    with pytest.raises(KeyError):
        format_publications([{"title": "Missing DOI"}])
