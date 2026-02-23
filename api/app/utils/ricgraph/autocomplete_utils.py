from app.utils.ricgraph.RicgraphAPI import execute_query

# module-scoped cache voor gedetecteerde index-namen
_PERSON_FT_INDEX = None
_ORG_FT_INDEX = None


# helpers
def _strip_hash(label: str) -> str:
    if not label:
        return ""
    i = label.find("#")
    return label[:i] if i != -1 else label


def _better_label(a: str, b: str) -> str:
    """Kies de ‘beste’ weergavenaam: voorkeur aan variant met komma (achternaam, initialen),
    anders de langste."""
    a, b = a or "", b or ""
    if ("," in a) != ("," in b):
        return a if "," in a else b
    return a if len(a) >= len(b) else b


def _detect_fulltext_indexes():
    """
    Leest SHOW INDEXES en kiest geschikte FULLTEXT indexen voor persons/orgs.
    Persons: voorkeur property 'value_ft' (zoals bij jou)
    Orgs:    voorkeur property 'value'
    """
    global _PERSON_FT_INDEX, _ORG_FT_INDEX
    if _PERSON_FT_INDEX and _ORG_FT_INDEX:
        return

    rows = execute_query(  # noqa: F821 (verwacht globale graph)
        "SHOW INDEXES YIELD name, type, labelsOrTypes, properties, state "
        "RETURN name, type, labelsOrTypes, properties, state",
    )

    # Helper om index te vinden op basis van property-voorkeur
    def pick(preferred_props):
        # prioriteer FULLTEXT op RicgraphNode met property in preferred_props en ONLINE
        for prop in preferred_props:
            for r in rows:
                if (
                    r.get("type") == "FULLTEXT"
                    and r.get("state") == "ONLINE"
                    and r.get("labelsOrTypes")
                    and "RicgraphNode" in r["labelsOrTypes"]
                    and r.get("properties")
                    and prop in r["properties"]
                ):
                    return r["name"]
        return None

    # Personen gebruiken bij jou value_ft
    _PERSON_FT_INDEX = pick(["value_ft", "value"])
    # Organisaties gebruiken bij jou value
    _ORG_FT_INDEX = pick(["value", "value_ft"])


def _pack(rows, category: str):
    out = []
    for r in rows:
        n = r.get("node") or {}
        out.append(
            {
                "value": n.get("_key") or n.get("id") or n.get("value"),
                "label": n.get("value") or n.get("name") or n.get("_key"),
                "category": category,
                "score": r.get("score", 1.0),
            }
        )
    return out


def _prefix_persons(term, limit):
    q = """
    MATCH (n:RicgraphNode {category:'person'})
    WHERE toLower(n.value) STARTS WITH toLower($term)
       OR (n.name IS NOT NULL AND toLower(n.name) STARTS WITH toLower($term))
    RETURN n AS node, 1.0 AS score
    ORDER BY n.value
    LIMIT $lim
    """
    rows = execute_query(q, term=term, lim=limit)
    return _pack(rows, "person")


def _prefix_orgs(term, limit):
    q = """
    MATCH (n:RicgraphNode {category:'organization'})
    WHERE toLower(n.value) STARTS WITH toLower($term)
       OR (n.name IS NOT NULL AND toLower(n.name) STARTS WITH toLower($term))
    RETURN n AS node, 1.0 AS score
    ORDER BY n.value
    LIMIT $lim
    """
    rows = execute_query(q, term=term, lim=limit)
    return _pack(rows, "organization")


def _dedupe_persons_by_value(items: list, limit: int) -> list:
    """Merge resultaten met dezelfde value (_key), strip #uuid in label, kies beste label."""
    by_val = {}
    for it in items:
        v = it.get("value")
        if not v:
            continue
        # strip #uuid alleen voor personen
        lab = _strip_hash(it.get("label") or "")
        if v in by_val:
            cur = by_val[v]
            # kies betere label
            cur["label"] = _better_label(cur.get("label"), lab)
            # hou hoogste score
            cur["score"] = max(cur.get("score", 0), it.get("score", 0))
        else:
            new_it = dict(it)
            new_it["label"] = lab
            by_val[v] = new_it
    # sorteer: eerst hoogste score, dan alfabetisch
    merged = sorted(
        by_val.values(), key=lambda x: (-x.get("score", 0), x.get("label") or "")
    )
    return merged[:limit]


def search_persons(query: str, limit: int = 10):
    term = (query or "").strip()
    if len(term) < 2:
        return []

    _detect_fulltext_indexes()  # zoals eerder

    persons = _prefix_persons(term, limit)
    remain = max(0, limit - len(persons))
    if remain > 0 and _PERSON_FT_INDEX:
        try:
            q = f"""
            CALL db.index.fulltext.queryNodes($_idx, $term)
            YIELD node, score
            WHERE node.category = 'person'
            // geef raw node terug; we strippen # in Python
            RETURN node AS node, score
            ORDER BY score DESC
            LIMIT $lim
            """
            extra = execute_query(q, _idx=_PERSON_FT_INDEX, term=term, lim=remain)
            persons += _pack(extra, "person")
        except Exception as e:
            print(f"[autocomplete] fulltext persons skipped ({_PERSON_FT_INDEX}): {e}")

    # 🔧 alleen voor personen: strip '#...' en de-dupe op value (_key)
    persons = _dedupe_persons_by_value(persons, limit)
    return persons


def search_organizations(query: str, limit: int = 10):
    term = (query or "").strip()
    if len(term) < 2:
        return []
    _detect_fulltext_indexes()

    orgs = _prefix_orgs(term, limit)
    remain = max(0, limit - len(orgs))
    if remain > 0 and _ORG_FT_INDEX:
        try:
            q = f"""
            CALL db.index.fulltext.queryNodes($_idx, $term)
            YIELD node, score
            WHERE node.category = 'organization'
            RETURN node, score
            ORDER BY score DESC
            LIMIT $lim
            """
            extra = execute_query(q, _idx=_ORG_FT_INDEX, term=term, lim=remain)
            orgs += _pack(extra, "organization")
        except Exception as e:
            print(f"[autocomplete] fulltext orgs skipped ({_ORG_FT_INDEX}): {e}")
    return orgs


def autocomplete(query: str, limit: int = 10):
    """Zoekt naar personen en organisaties die matchen op query. Combineert prefix search en fulltext search."""
    persons = search_persons(query, limit)
    orgs = search_organizations(query, limit)

    # Convert internal format {"value","label",...} -> API schema expected fields
    # Person schema expects: {"author_id": str, "name": str}
    # Organization schema expects: {"organization_id": str, "name": str}
    persons_out = []
    for p in persons:
        # skip malformed items
        val = p.get("value")
        lab = p.get("label")
        if not val or not lab:
            continue
        persons_out.append({"author_id": val, "name": lab})

    orgs_out = []
    for o in orgs:
        val = o.get("value")
        lab = o.get("label")
        if not val or not lab:
            continue
        orgs_out.append({"organization_id": val, "name": lab})

    return {"persons": persons_out, "organizations": orgs_out}
