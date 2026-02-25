from typing import Any, Dict, List

from app.utils.ricgraph.RicgraphAPI import execute_query
from app.utils.ricgraph.autocomplete_utils import clean_label

PUBLICATION_CATEGORIES = [
    "journal-article",
    "conference-paper",
    "book",
    "book-chapter",
    "report",
    "review",
    "dataset",
    "preprint",
]


def fetch_publications(entity_key: str) -> List[Dict[str, Any]]:
    """2-hop: entity -- mid -- pub where pub is a publication category."""
    query = """
    MATCH (entity:RicgraphNode {_key: $key})--(mid)--(pub:RicgraphNode)
    WHERE pub.category IN $cats
    RETURN DISTINCT pub AS node
    ORDER BY pub.value
    LIMIT 50
    """
    try:
        rows = execute_query(query, key=entity_key, cats=PUBLICATION_CATEGORIES)
        results = []
        seen = set()
        for row in rows:
            node = row.get("node") or {}
            key = node.get("_key")
            if not key or key in seen:
                continue
            seen.add(key)
            value = clean_label(node.get("value", ""))
            if not value:
                continue
            results.append({
                "doi": value,
                "title": value,
                "year": node.get("year"),
                "category": node.get("category", ""),
            })
        return results
    except Exception:
        return []


def fetch_collaborators(entity_key: str) -> List[Dict[str, Any]]:
    """4-hop: person -- r1 -- pub -- r2 -- collab (co-authors via shared publications)."""
    query = """
    MATCH (person:RicgraphNode {_key: $key})--(r1)--(pub)--(r2)--(collab:RicgraphNode {category: 'person'})
    WHERE person <> collab
    RETURN DISTINCT collab AS node
    ORDER BY collab.value
    LIMIT 50
    """
    try:
        rows = execute_query(query, key=entity_key)
        results = []
        seen = set()
        for row in rows:
            node = row.get("node") or {}
            key = node.get("_key")
            if not key or key in seen:
                continue
            seen.add(key)
            name = clean_label(node.get("value", ""))
            if not name:
                continue
            results.append({
                "author_id": key,
                "name": name,
            })
        return results
    except Exception:
        return []


def fetch_organizations(entity_key: str) -> List[Dict[str, Any]]:
    """2-hop: entity -- mid -- org where org.category = 'organization'."""
    query = """
    MATCH (entity:RicgraphNode {_key: $key})--(mid)--(org:RicgraphNode {category: 'organization'})
    RETURN DISTINCT org AS node
    ORDER BY org.value
    LIMIT 50
    """
    try:
        rows = execute_query(query, key=entity_key)
        results = []
        seen = set()
        for row in rows:
            node = row.get("node") or {}
            key = node.get("_key")
            if not key or key in seen:
                continue
            seen.add(key)
            name = clean_label(node.get("value", ""))
            if not name:
                continue
            results.append({
                "organization_id": key,
                "name": name,
            })
        return results
    except Exception:
        return []


def fetch_members(org_key: str) -> List[Dict[str, Any]]:
    """2-hop: org -- mid -- person where person.category = 'person'."""
    query = """
    MATCH (org:RicgraphNode {_key: $key})--(mid)--(person:RicgraphNode {category: 'person'})
    RETURN DISTINCT person AS node
    ORDER BY person.value
    LIMIT 50
    """
    try:
        rows = execute_query(query, key=org_key)
        results = []
        seen = set()
        for row in rows:
            node = row.get("node") or {}
            key = node.get("_key")
            if not key or key in seen:
                continue
            seen.add(key)
            name = clean_label(node.get("value", ""))
            if not name:
                continue
            results.append({
                "author_id": key,
                "name": name,
            })
        return results
    except Exception:
        return []
