from typing import Any

from app.utils.schemas import Person, Publication, Organization
from app.utils.schemas.connections import Member

PeopleOrMembers = Person | Member

def clean_name(raw: str | None) -> str:
    """Normalize a raw person name from graph values."""
    if not raw:
        return ""
    name = raw.split("#")[0].strip()
    return name[1:].strip() if name.startswith(",") else name

def clean_title(raw: Any) -> str | None:
    """Normalize title values from mixed query payload shapes."""
    if raw is None:
        return None
    if isinstance(raw, list):
        if not raw:
            return None
        first = raw[0]
        if isinstance(first, str):
            return first.strip() or None
        return None
    if isinstance(raw, str):
        return raw.strip() or None
    return None

def parse_year(raw: Any) -> int | None:
    """Parse a year value into an integer when possible."""
    if isinstance(raw, bool):
        return None
    if isinstance(raw, int):
        return raw
    if isinstance(raw, str) and raw.strip():
        try:
            return int(raw)
        except ValueError:
            return None
    return None

def format_people(rows: list[dict[str, Any]], *, as_members: bool = False) -> list[PeopleOrMembers]:
    """Format person rows as Person or Member models."""
    out: list[PeopleOrMembers] = []
    for row in rows:
        name = clean_name(row.get("rawName"))
        sort_name = row.get("sort_name") if isinstance(row.get("sort_name"), str) else None
        if as_members:
            out.append(Member(author_id=row["author_id"], name=name, sort_name=sort_name))
        else:
            out.append(Person(author_id=row["author_id"], name=name, sort_name=sort_name))
    return out

def format_organizations(rows: list[dict[str, Any]]) -> list[Organization]:
    """Convert organization query rows into Organization models."""
    return [Organization(organization_id=row["organization_id"], name=row["name"]) for row in rows]

def normalize_versions(raw_versions: Any) -> list[dict[str, Any]] | None:
    """Normalize optional publication version payloads."""
    if not isinstance(raw_versions, list):
        return None

    versions: list[dict[str, Any]] = []
    for version in raw_versions:
        if not isinstance(version, dict):
            continue
        doi = version.get("doi")
        if not isinstance(doi, str) or not doi.strip():
            continue
        versions.append(
            {
                "doi": doi.strip(),
                "year": parse_year(version.get("year")),
                "category": version.get("category"),
            }
        )
    return versions or None

def format_publications(rows: list[dict[str, Any]]) -> list[Publication]:
    """Convert publication rows into Publication models preserving query order."""
    publications: list[Publication] = []
    for row in rows:
        publications.append(
            Publication(
                doi=row["doi"],
                title=clean_title(row.get("title")),
                year=parse_year(row.get("year")),
                category=row.get("category"),
                versions=normalize_versions(row.get("versions")),
            )
        )
    return publications
