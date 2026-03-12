"""Tests for Pydantic schema validation."""

import pytest
from pydantic import ValidationError

from app.utils.schemas import (
    Person, Organization, Suggestions, Connections, Member,
    ChatRequest, EmbedRequest, EntityRef, Message, RagGenerateRequest,
)


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
            members=[Member(author_id="p1", name="John")],
        )
        assert c.members[0].name == "John"


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


class TestMessage:
    def test_valid_message(self):
        m = Message(role="user", content="hello")
        assert m.role == "user"
        assert m.content == "hello"

    def test_missing_role(self):
        with pytest.raises(ValidationError):
            Message(content="hello")

    def test_missing_content(self):
        with pytest.raises(ValidationError):
            Message(role="user")


class TestChatRequest:
    def test_defaults(self):
        req = ChatRequest(messages=[Message(role="user", content="hi")])
        assert req.stream is True
        assert req.options is None
        assert req.model  # has a default from CHAT_MODEL

    def test_custom_model(self):
        req = ChatRequest(model="llama3", messages=[Message(role="user", content="hi")])
        assert req.model == "llama3"

    def test_missing_messages(self):
        with pytest.raises(ValidationError):
            ChatRequest()

    def test_with_options(self):
        req = ChatRequest(
            messages=[Message(role="user", content="hi")],
            options={"temperature": 0.7},
        )
        assert req.options["temperature"] == 0.7

    def test_serialization_excludes_none(self):
        req = ChatRequest(messages=[Message(role="user", content="hi")])
        data = req.model_dump(exclude_none=True)
        assert "options" not in data


class TestEmbedRequest:
    def test_defaults(self):
        req = EmbedRequest(prompt="test text")
        assert req.prompt == "test text"
        assert req.model  # has a default from EMBED_MODEL

    def test_custom_model(self):
        req = EmbedRequest(model="custom-embed", prompt="test")
        assert req.model == "custom-embed"

    def test_missing_prompt(self):
        with pytest.raises(ValidationError):
            EmbedRequest()


class TestEntityRef:
    def test_valid_person(self):
        e = EntityRef(id="p1", type="person", label="John Doe")
        assert e.type == "person"

    def test_valid_organization(self):
        e = EntityRef(id="o1", type="organization", label="Utrecht University")
        assert e.type == "organization"

    def test_invalid_type_rejected(self):
        with pytest.raises(ValidationError):
            EntityRef(id="x1", type="unknown", label="Bad")

    def test_missing_fields(self):
        with pytest.raises(ValidationError):
            EntityRef(id="p1")


class TestRagGenerateRequest:
    def test_defaults(self):
        req = RagGenerateRequest(prompt="What does this researcher study?")
        assert req.top_k == 8
        assert req.entity is None

    def test_with_entity(self):
        req = RagGenerateRequest(
            prompt="Tell me about their work",
            entity=EntityRef(id="p1", type="person", label="John"),
        )
        assert req.entity.id == "p1"
        assert req.entity.type == "person"

    def test_custom_top_k(self):
        req = RagGenerateRequest(prompt="test", top_k=20)
        assert req.top_k == 20

    def test_missing_prompt(self):
        with pytest.raises(ValidationError):
            RagGenerateRequest()
