"""Tests for Pydantic schema validation."""

import pytest
from pydantic import ValidationError

from app.utils.schemas import Person, Organization, Suggestions, Connections, Member


class TestPerson:
    def test_valid_person(self):
        p = Person(author_id="abc123", name="John Doe")
        assert p.author_id == "abc123"
        assert p.name == "John Doe"

    def test_missing_author_id(self):
        with pytest.raises(ValidationError):
            Person(name="John Doe")

    def test_missing_name(self):
        with pytest.raises(ValidationError):
            Person(author_id="abc123")


class TestOrganization:
    def test_valid_organization(self):
        o = Organization(organization_id="org1", name="Utrecht University")
        assert o.organization_id == "org1"
        assert o.name == "Utrecht University"

    def test_missing_fields(self):
        with pytest.raises(ValidationError):
            Organization(name="Utrecht University")


class TestSuggestions:
    def test_valid_suggestions(self):
        s = Suggestions(
            persons=[Person(author_id="p1", name="John")],
            organizations=[Organization(organization_id="o1", name="UU")],
        )
        assert len(s.persons) == 1
        assert len(s.organizations) == 1

    def test_empty_suggestions(self):
        s = Suggestions(persons=[], organizations=[])
        assert s.persons == []
        assert s.organizations == []

    def test_serialization(self):
        s = Suggestions(
            persons=[Person(author_id="p1", name="John")],
            organizations=[],
        )
        data = s.model_dump()
        assert data["persons"][0]["author_id"] == "p1"
        assert data["organizations"] == []


class TestConnections:
    def test_valid_connections(self):
        c = Connections(
            entity_id="p1",
            entity_type="person",
            collaborators=[Person(author_id="p2", name="Jane")],
            publications=[],
            organizations=[],
            members=[],
        )
        assert c.entity_id == "p1"
        assert len(c.collaborators) == 1

    def test_missing_entity_id(self):
        with pytest.raises(ValidationError):
            Connections(
                entity_type="person",
                collaborators=[], publications=[],
                organizations=[], members=[],
            )

    def test_with_members(self):
        c = Connections(
            entity_id="o1",
            entity_type="organization",
            collaborators=[],
            publications=[],
            organizations=[],
            members=[Member(author_id="p1", name="John", role="Professor")],
        )
        assert c.members[0].role == "Professor"

    def test_member_role_optional(self):
        m = Member(author_id="p1", name="John")
        assert m.role is None


class TestPublication:
    def test_minimal_publication(self):
        from app.utils.schemas import Publication
        p = Publication(doi="10.1/test")
        assert p.doi == "10.1/test"
        assert p.title is None
        assert p.year is None
        assert p.versions is None

    def test_full_publication(self):
        from app.utils.schemas import Publication
        p = Publication(
            doi="10.1/test", title="Paper", year=2024,
            category="article", name="Author",
            publication_rootid="root-1",
            versions=[{"doi": "10.1/v2", "year": 2023, "category": "preprint"}],
        )
        assert p.versions is not None
        assert len(p.versions) == 1
