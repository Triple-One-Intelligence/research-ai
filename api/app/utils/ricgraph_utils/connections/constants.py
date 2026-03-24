from typing import Literal

class ConnectionsError(RuntimeError):
    pass

class InvalidEntityTypeError(ValueError):
    pass

class InvalidCursorError(ValueError):
    pass

EXCLUDE_CATEGORIES: tuple[str, ...] = ()
"""Categories of publications to exclude from connections queries."""

EntityType = Literal["person", "organization"]
VALID_ENTITY_TYPES: set[EntityType] = {"person", "organization"}

def validate_entity_type(entity_type: str) -> None:
    if entity_type not in VALID_ENTITY_TYPES:
        raise InvalidEntityTypeError("entity_type must be 'person' or 'organization'")
