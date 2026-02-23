from app.utils.ricgraph.RicgraphAPI import execute_query
from app.utils.schemas import Suggestions

def strip_hash(label: str) -> str:
    """Remove trailing #uuid fragments and tidy whitespace/leading commas."""
    if not label:
        return ""
    # Remove trailing #... fragment
    idx = label.find("#")
    res = label[:idx] if idx != -1 else label
    # Trim whitespace and strip a leading comma if present
    res = res.strip()
    if res.startswith(","):
        res = res.lstrip(",").strip()
    return res

def choose_better_label(a: str, b: str) -> str:
    """Choose the 'best' display name: prefer the variant with a comma (last name, initials),
    otherwise the longest."""
    a = a or ""
    b = b or ""

    if ("," in a) != ("," in b):
        return a if "," in a else b

    return a if len(a) >= len(b) else b

def sanitize_id(raw):
    """Normalize a raw id-like string from the node._key:
    - If present, take the part before '|' (strip metadata suffix)
    - Remove trailing '#...' fragments
    - Trim whitespace and remove leading commas
    Returns None if raw is falsy.
    """
    if not raw:
        return None
    if not isinstance(raw, str):
        return raw
    # First remove any pipe-suffix metadata
    val = raw.split("|", 1)[0]
    # Then remove trailing #... fragments
    val = val.split("#", 1)[0]
    # Trim and remove leading comma if present
    val = val.strip()
    if val.startswith(","):
        val = val.lstrip(",").strip()
    return val or None

def pack(rows, category: str):
    out = []
    for row in rows:
        node = row.get("node") or {}
        # Require a canonical _key; skip nodes without it
        raw_key = node.get("_key")
        if not raw_key:
            continue

        value = sanitize_id(raw_key)
        if not value:
            continue

        # In Ricgraph, node.name is the property type (e.g. "FULL_NAME", "SCOPUS_AUTHOR_ID")
        # node.value is the actual value (e.g. "John Doe", "12345")
        # So the label MUST be based on node.value, NOT node.name.
        raw_value = node.get("value")

        if raw_value and str(raw_value).strip():
            label = strip_hash(str(raw_value))
        else:
            label = value

        out.append(
            {
                "value": value,
                "label": label,
                "category": category,
                "score": row.get("score", 1.0),
            }
        )
    return out

def search_prefix_persons(term, limit):
    query = """
    MATCH (n:RicgraphNode {category:'person'})
    WHERE toLower(n.value) STARTS WITH toLower($term)
    RETURN n AS node, 1.0 AS score
    ORDER BY n.value
    LIMIT $lim
    """
    rows = execute_query(query, term=term, lim=limit)
    return pack(rows, "person")

def prefix_orgs(term, limit):
    query = """
    MATCH (n:RicgraphNode {category:'organization'})
    WHERE toLower(n.value) STARTS WITH toLower($term)
    RETURN n AS node, 1.0 AS score
    ORDER BY n.value
    LIMIT $lim
    """
    rows = execute_query(query, term=term, lim=limit)
    return pack(rows, "organization")

def parse_persons(persons: list, limit: int) -> list:
    """Merge persons with the same value (_key), strip #uuid in label, choose best label."""
    values = {}
    for person in persons:
        value = person.get("value")
        if not value:
            continue

        label = strip_hash(person.get("label") or "")
        if value in values:
            current_person = values[value]
            current_person["label"] = choose_better_label(current_person.get("label"), label)
            current_person["score"] = max(current_person.get("score", 0), person.get("score", 0))
        else:
            new_person = dict(person)
            new_person["label"] = label
            values[value] = new_person

    # Sort: Highest score first, then alphabetically
    merged = sorted(values.values(), key=lambda x: (-x.get("score", 0), x.get("label") or ""))
    return merged[:limit]

def search_persons(term: str, limit: int = 10):
    # 1) prefix matches
    persons = search_prefix_persons(term, limit)
    persons = parse_persons(persons, limit)

    # 2) if we need more, search for term anywhere using CONTAINS
    remain = max(0, limit - len(persons))
    if remain > 0:
        excludes = [p["value"] for p in persons if p.get("value")]

        base_query = """
        MATCH (n:RicgraphNode {category:'person'})
        WHERE toLower(n.value) CONTAINS toLower($term)
        RETURN n AS node, 1.0 AS score
        ORDER BY n.value
        LIMIT $lim
        """

        query_with_excludes = """
        MATCH (n:RicgraphNode {category:'person'})
        WHERE toLower(n.value) CONTAINS toLower($term)
          AND NOT (n._key IN $excludes)
        RETURN n AS node, 1.0 AS score
        ORDER BY n.value
        LIMIT $lim
        """

        if excludes:
            extra = execute_query(query_with_excludes, term=term, excludes=excludes, lim=remain)
        else:
            extra = execute_query(base_query, term=term, lim=remain)

        persons += pack(extra, "person")

    persons = parse_persons(persons, limit)
    return persons

def search_organizations(term: str, limit: int = 10):
    orgs = prefix_orgs(term, limit)

    remain = max(0, limit - len(orgs))
    if remain > 0:
        excludes = [o["value"] for o in orgs if o.get("value")]

        base_query = """
        MATCH (n:RicgraphNode {category:'organization'})
        WHERE toLower(n.value) CONTAINS toLower($term)
        RETURN n AS node, 1.0 AS score
        ORDER BY n.value
        LIMIT $lim
        """

        query_with_excludes = """
        MATCH (n:RicgraphNode {category:'organization'})
        WHERE toLower(n.value) CONTAINS toLower($term)
          AND NOT (n._key IN $excludes)
        RETURN n AS node, 1.0 AS score
        ORDER BY n.value
        LIMIT $lim
        """

        if excludes:
            extra = execute_query(query_with_excludes, term=term, excludes=excludes, lim=remain)
        else:
            extra = execute_query(base_query, term=term, lim=remain)

        orgs += pack(extra, "organization")

    return orgs

def format_for_api(items: list, id_field_name: str) -> list:
    """Generic formatter converting internal items to the API schema:
    items are expected to have 'value' and 'label'. The id_field_name should be
    either 'author_id' or 'organization_id' depending on the schema required.
    """
    return [
        {id_field_name: item["value"], "name": item["label"]}
        for item in items
        if item.get("value") and item.get("label")
    ]

def autocomplete(query: str, limit: int = 10):
    """Searches for persons and organizations matching the query. Combines prefix search and fulltext search."""

    term = (query or "").strip()
    if len(term) < 2:
        return []

    persons = search_persons(term, limit)
    organizations = search_organizations(term, limit)

    persons_out = format_for_api(persons, "author_id")
    orgs_out = format_for_api(organizations, "organization_id")

    return Suggestions(persons=persons_out, organizations=orgs_out)
