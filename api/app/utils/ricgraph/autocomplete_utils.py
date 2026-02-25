"""
Autocomplete utilities.

This module provides the ``autocomplete`` helper used by the autocomplete
router. This module is responsible only for
calling that dedicated endpoint and mapping the raw rows into the
``Suggestions`` pydantic model consumed by the API layer.
"""

from app.utils.ricgraph.ricgraph_api import autocomplete_search
from app.utils.schemas import Suggestions


def autocomplete(user_query: str, limit: int = 10) -> Suggestions:
    """
    Autocomplete search function.

    Calls ``/autocomplete`` endpoint, then maps the returned
    rows into the ``Suggestions`` response model.

    Parameters
    - user_query: the partial text to autocomplete
    - limit: maximum number of suggestions to return

    Returns
    - Suggestions pydantic model instance
    """
    try:
        rows = autocomplete_search(query=user_query, limit=limit)
    except Exception as e:
        print(f"Autocomplete search failed for query '{user_query}': {e}")
        return Suggestions(persons=[], organizations=[])

    persons_out = []
    orgs_out = []

    for row in rows:
        if row.get("type") == "person":
            persons_out.append({
                "author_id": row["id"],
                "name": row["displayName"],
            })
        elif row.get("type") == "organization":
            orgs_out.append({
                "organization_id": row["id"],
                "name": row["displayName"],
            })

    return Suggestions(persons=persons_out, organizations=orgs_out)
