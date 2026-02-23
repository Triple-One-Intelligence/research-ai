from app.utils.ricgraph.RicgraphAPI import execute_query
from app.utils.schemas import Suggestions

def strip_hash(label: str) -> str:
    """Remove trailing #uuid fragments and tidy leading/trailing whitespace/commas."""
    if not label:
        return ""
    idx = label.find("#")
    res = label[:idx] if idx != -1 else label
    res = res.strip()
    # Remove a leading comma if present (e.g. ", Foo Bar" -> "Foo Bar")
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
    """Normalize a raw id-like string from the node:
    - prefer the part before '|' if present
    - strip trailing '#...' fragments
    - trim whitespace
    Return None if raw is empty/None.
    """
    if not raw:
        return None
    if not isinstance(raw, str):
        return raw
    val = raw.split("|", 1)[0]
    val = val.split("#", 1)[0]
    return val.strip()

def pack(rows, category: str):
    out = []
    for row in rows:
        node = row.get("node") or {}
        raw_value = node.get("_key") or node.get("id") or node.get("value")
        value = sanitize_id(raw_value)
        raw_label = node.get("value") or node.get("name") or node.get("_key")
        label = strip_hash(raw_label or "")
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
       OR (n.name IS NOT NULL AND toLower(n.name) STARTS WITH toLower($term))
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
       OR (n.name IS NOT NULL AND toLower(n.name) STARTS WITH toLower($term))
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
    # 1) prefix matches (fast-ish, still no index used if not present)
    persons = search_prefix_persons(term, limit)
    persons = parse_persons(persons, limit)

    # debug: how many prefix results
    print(f"[autocomplete-debug] term={term!r} prefix_count={len(persons)} prefix_values={[p.get('value') for p in persons][:10]}")

    # 2) if we need more, search for term anywhere using CONTAINS
    remain = max(0, limit - len(persons))
    if remain > 0:
        # build exclude list of values (prefer _key)
        excludes = [p["value"] for p in persons if p.get("value")]
        # Base query (without excludes)
        base_query = """
        MATCH (n:RicgraphNode {category:'person'})
        WHERE (toLower(n.value) CONTAINS toLower($term)
           OR (n.name IS NOT NULL AND toLower(n.name) CONTAINS toLower($term)))
        RETURN n AS node, 1.0 AS score
        ORDER BY n.value
        LIMIT $lim
        """
        # Query with excludes clause
        query_with_excludes = """
        MATCH (n:RicgraphNode {category:'person'})
        WHERE (toLower(n.value) CONTAINS toLower($term)
           OR (n.name IS NOT NULL AND toLower(n.name) CONTAINS toLower($term)))
          AND NOT (n._key IN $excludes)
        RETURN n AS node, 1.0 AS score
        ORDER BY n.value
        LIMIT $lim
        """

        # debug: print the params we will pass
        print(f"[autocomplete-debug] running CONTAINS fallback, remain={remain}, excludes_count={len(excludes)}")

        if excludes:
            extra = execute_query(query_with_excludes, term=term, excludes=excludes, lim=remain)
        else:
            extra = execute_query(base_query, term=term, lim=remain)

        extra_count = len(extra) if extra else 0
        print(f"[autocomplete-debug] CONTAINS returned {extra_count} rows")
        try:
            sample_vals = [r.get('node', {}).get('value') or r.get('node', {}).get('name') for r in (extra or [])][:10]
            print(f"[autocomplete-debug] CONTAINS sample values: {sample_vals}")
        except Exception:
            pass

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
        WHERE (toLower(n.value) CONTAINS toLower($term)
           OR (n.name IS NOT NULL AND toLower(n.name) CONTAINS toLower($term)))
        RETURN n AS node, 1.0 AS score
        ORDER BY n.value
        LIMIT $lim
        """
        query_with_excludes = """
        MATCH (n:RicgraphNode {category:'organization'})
        WHERE (toLower(n.value) CONTAINS toLower($term)
           OR (n.name IS NOT NULL AND toLower(n.name) CONTAINS toLower($term)))
          AND NOT (n._key IN $excludes)
        RETURN n AS node, 1.0 AS score
        ORDER BY n.value
        LIMIT $lim
        """

        print(f"[autocomplete-debug] running ORG CONTAINS fallback, remain={remain}, excludes_count={len(excludes)}")

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
