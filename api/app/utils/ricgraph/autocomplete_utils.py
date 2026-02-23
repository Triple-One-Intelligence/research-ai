from app.utils.ricgraph.RicgraphAPI import execute_query
from app.utils.schemas import Suggestions

# Module-scoped cache for detected index-names
_PERSON_FT_INDEX = None
_ORG_FT_INDEX = None

# Debug
print(execute_query("SHOW INDEXES YIELD name, type, labelsOrTypes, properties, state RETURN name, type, labelsOrTypes, properties, state"))
print(execute_query("CALL db.index.fulltext.list() YIELD * RETURN *"))


def strip_hash(label: str) -> str:
    if not label:
        return ""
    index = label.find("#")
    return label[:index] if index != -1 else label

def choose_better_label(a: str, b: str) -> str:
    """Choose the 'best' display name: prefer the variant with a comma (last name, initials),
    otherwise the longest."""
    a = a or ""
    b = b or ""

    if ("," in a) != ("," in b):
        return a if "," in a else b

    return a if len(a) >= len(b) else b

def detect_fulltext_indexes():
    """
    Reads SHOW INDEXES and chooses appropriate FULLTEXT indexes for persons/orgs.
    Persons: preferred property 'value_ft' (as in your setup)
    Orgs:    preferred property 'value'
    """
    global _PERSON_FT_INDEX, _ORG_FT_INDEX
    if _PERSON_FT_INDEX and _ORG_FT_INDEX:
        return

    rows = execute_query(
        "SHOW INDEXES YIELD name, type, labelsOrTypes, properties, state "
        "RETURN name, type, labelsOrTypes, properties, state"
    )

    # Helper to find index based on property preference
    def pick(preferred_properties):
        # prioritize FULLTEXT on RicgraphNode with property in preferred_properties and ONLINE
        for property in preferred_properties:
            for row in rows:
                if (
                    row.get("type") == "FULLTEXT"
                    and row.get("state") == "ONLINE"
                    and row.get("labelsOrTypes")
                    and "RicgraphNode" in row["labelsOrTypes"]
                    and row.get("properties")
                    and property in row["properties"]
                ):
                    return row["name"]
        return None

    _PERSON_FT_INDEX = pick(["value_ft", "value"])
    _ORG_FT_INDEX = pick(["value", "value_ft"])

    print(f"Detected person fulltext index: {_PERSON_FT_INDEX}, org index: {_ORG_FT_INDEX}")


def pack(rows, category: str):
    out = []
    for row in rows:
        node = row.get("node") or {}
        out.append(
            {
                "value": node.get("_key") or node.get("id") or node.get("value"),
                "label": node.get("value") or node.get("name") or node.get("_key"),
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
    # Get persons which have the term as prefix
    persons = search_prefix_persons(term, limit)

    persons = parse_persons(persons, limit)

    # If any space remains to return more persons, use the full text indices
    remain = max(0, limit - len(persons))
    if remain > 0 and _PERSON_FT_INDEX:
        try:
            query = """
            CALL db.index.fulltext.queryNodes($_idx, $term)
            YIELD node, score
            WHERE node.category = 'person'
            // return raw node; we strip # in Python
            RETURN node AS node, score
            ORDER BY score DESC
            LIMIT $lim
            """
            extra = execute_query(query, _idx=_PERSON_FT_INDEX, term=term+"*", lim=remain)
            persons += pack(extra, "person")
        except Exception as e:
            print(f"[autocomplete] fulltext persons skipped ({_PERSON_FT_INDEX}): {e}")

    persons = parse_persons(persons, limit)

    return persons

def search_organizations(term: str, limit: int = 10):

    # Get the organizations which have the term as prefix
    orgs = prefix_orgs(term, limit)

    # If any space remains to return more organizations, use the full text indices
    remain = max(0, limit - len(orgs))
    if remain > 0 and _ORG_FT_INDEX:
        try:
            query = """
            CALL db.index.fulltext.queryNodes($_idx, $term)
            YIELD node, score
            WHERE node.category = 'organization'
            RETURN node, score
            ORDER BY score DESC
            LIMIT $lim
            """
            extra = execute_query(query, _idx=_ORG_FT_INDEX, term=term, lim=remain)
            orgs += pack(extra, "organization")
        except Exception as e:
            print(f"[autocomplete] fulltext orgs skipped ({_ORG_FT_INDEX}): {e}")
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

    detect_fulltext_indexes()

    persons = search_persons(term, limit)
    organizations = search_organizations(term, limit)

    persons_out = format_for_api(persons, "author_id")
    orgs_out = format_for_api(organizations, "organization_id")

    return Suggestions(persons=persons_out, organizations=orgs_out)
