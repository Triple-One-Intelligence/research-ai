import base64
import json
from collections.abc import Callable
from typing import Any, TypeVar

from app.utils.schemas import Publication, Organization

from .constants import InvalidCursorError

def publication_sort_key(title: str | None, doi: str) -> str:
    """Build the same sort key used by publication Cypher queries."""
    normalized_title = (title or "").strip()
    return f"title:{normalized_title.lower()}" if normalized_title else f"doi:{doi}"

def encode_cursor(payload: dict[str, Any]) -> str:
    """Encode cursor payload as URL-safe base64 JSON."""
    encoded = base64.urlsafe_b64encode(json.dumps(payload).encode("utf-8")).decode("utf-8")
    return encoded.rstrip("=")

def decode_cursor(cursor: str | None, required_keys: tuple[str, ...]) -> dict[str, str]:
    """Decode cursor payload and return validated string keys only."""
    if not cursor:
        return {}
    try:
        # Cursors are urlsafe base64 strings without "=" padding.
        padding = "=" * (-len(cursor) % 4)
        decoded = base64.urlsafe_b64decode((cursor + padding).encode("utf-8")).decode("utf-8")
        payload = json.loads(decoded)
    except Exception as exception:
        raise InvalidCursorError("Invalid pagination cursor") from exception
    if not isinstance(payload, dict):
        raise InvalidCursorError("Invalid pagination cursor")
    values: dict[str, str] = {}
    for key in required_keys:
        value = payload.get(key)
        if not isinstance(value, str) or not value:
            raise InvalidCursorError("Invalid pagination cursor")
        values[key] = value
    return values

def decode_cursor_pair(
    cursor: str | None,
    first_key: str,
    second_key: str,
) -> tuple[str | None, str | None]:
    """Decode a two-key cursor payload and return the values in order."""
    payload = decode_cursor(cursor, (first_key, second_key))
    return payload.get(first_key), payload.get(second_key)

def extract_cursor(
    items: list[Any],
    limit: int,
    *,
    id_attr: str,
    encode: Callable[..., str],
    name_attr: str | None = None,
    fallback_name_attr: str | None = None,
) -> str | None:
    """Build next-page cursor when we have an extra row (limit+1 strategy)."""
    # We request `limit + 1`; extra item means there is a next page.
    if not items or len(items) <= limit or limit < 1:
        return None

    last_item = items[limit - 1]
    item_id = getattr(last_item, id_attr, None)
    if not isinstance(item_id, str) or not item_id:
        return None

    if name_attr is None:
        return encode(item_id)

    name = getattr(last_item, name_attr, None)
    if (not isinstance(name, str) or not name) and fallback_name_attr:
        fallback_name = getattr(last_item, fallback_name_attr, None)
        name = fallback_name if isinstance(fallback_name, str) else None
    if not isinstance(name, str) or not name.strip():
        return None

    return encode(name, item_id)

def extract_people_cursor(people: list[Any], limit: int) -> str | None:
    """Build next-page cursor for people/member lists."""
    return extract_cursor(
        people,
        limit,
        id_attr="author_id",
        name_attr="sort_name",
        fallback_name_attr="name",
        encode=lambda name, author_id: encode_cursor({"name": name, "author_id": author_id}),
    )

def extract_organization_cursor(organizations: list[Organization], limit: int) -> str | None:
    """Build next-page cursor for organization lists."""
    return extract_cursor(
        organizations,
        limit,
        id_attr="organization_id",
        name_attr="name",
        encode=lambda name, organization_id: encode_cursor(
            {"name": name.lower(), "organization_id": organization_id}
        ),
    )

def extract_publication_cursor(publications: list[Publication], limit: int) -> str | None:
    """Build next-page cursor for publication lists."""
    return extract_cursor(
        publications,
        limit,
        id_attr="doi",
        name_attr="title",
        encode=lambda title, doi: encode_cursor(
            {"sort_key": publication_sort_key(title, doi), "doi": doi}
        ),
    )

T = TypeVar("T")

def trim_page(items: list[T], limit: int) -> list[T]:
    """Trim a limit+1 page back to limit items for response payloads."""
    if limit < 1:
        return []
    return items[:limit]
