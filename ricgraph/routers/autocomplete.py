"""
Autocomplete router for the Ricgraph Query API.

Provides the POST /autocomplete endpoint that returns suggestions
for partial search queries by matching against a Neo4j fulltext index
on RicgraphNode.value.
"""

import re
from typing import Any
from fastapi import APIRouter, HTTPException
from neo4j import Result
from pydantic import BaseModel, Field
from database import graph, FULLTEXT_INDEX_NAME

router = APIRouter()

# Lucene reserved characters that must be escaped
LUCENE_SPECIAL = re.compile(r'([+\-&|!(){}\[\]^"~*?:\\/])')

def escape_lucene(term: str) -> str:
    """Escape Lucene special characters in a search term."""
    return LUCENE_SPECIAL.sub(r'\\\1', term)

def build_lucene_query(keywords: list[str]) -> str:
    """
    Build a Lucene query string for autocomplete.

    Every keyword gets a wildcard suffix so partial input matches.
    All keywords are AND-joined so every term must be present.

    Example: ["henk", "boer"] -> "henk* AND boer*"
    """
    parts = [f"{escape_lucene(keyword)}*" for keyword in keywords]
    return " AND ".join(parts)

class AutocompleteRequest(BaseModel):
    """
    Incoming request model for the /autocomplete endpoint.

    Parameters
    - query: str (required) -- the partial text to autocomplete
    - limit: int (optional) -- maximum number of suggestions to return (default 10, range 1-100)
    """
    query: str
    limit: int = Field(default=10, ge=1, le=100)

AUTOCOMPLETE_CYPHER = """
    CALL db.index.fulltext.queryNodes($indexName, $luceneQuery)
    YIELD node, score AS ftScore
    WHERE node.category IN ['person', 'organization']
    AND NOT node.name ENDS WITH '-root'

    // Use fulltext score for initial ordering, limit early for performance
    WITH node
    ORDER BY ftScore DESC, size(node.value) ASC
    LIMIT 1000

    // Data cleaning (uuid + leading comma)
    WITH node, trim(split(node.value, '#')[0]) AS rawClean
    WITH node, CASE WHEN rawClean STARTS WITH ',' THEN trim(substring(rawClean, 1)) ELSE rawClean END AS name

    // Clean the DB name as well for comparison
    WITH node, name,
         toLower(reduce(s = name, char IN [',','.','-'] | replace(s, char, ' '))) AS dbCleanName

    // Ensure all keywords match the actual name, not the UUID part of the value
    WHERE all(k IN $keywords WHERE dbCleanName CONTAINS k)

    WITH node, name,
         CASE
            WHEN dbCleanName = $cleanQuery THEN 100
            WHEN toLower(name) STARTS WITH $firstKeyword THEN 50
            ELSE 10
         END AS matchScore,
         CASE
            WHEN name CONTAINS ',' THEN 3
            WHEN name CONTAINS ' ' THEN 2
            ELSE 1
         END AS formatScore

    WITH node._key AS id, name, node.category AS type, matchScore, formatScore
    ORDER BY formatScore DESC, size(name) DESC

    WITH id, type,
         head(collect(name)) AS displayName,
         max(matchScore) AS bestScore

    // Collapse different nodes that clean to the same
    // display name (e.g. full_name vs full_name_ascii variants, or duplicate
    // source nodes). min(id) prefers |full_name over
    // |full_name_ascii since the former is smaller.
    WITH displayName, type,
         max(bestScore) AS bestScore,
         min(id) AS id

    RETURN id, displayName, type, bestScore
    ORDER BY bestScore DESC, displayName ASC
    LIMIT $limit
"""

@router.post("/autocomplete")
def autocomplete(request: AutocompleteRequest) -> list[dict[str, Any]]:
    """
    Endpoint POST /autocomplete

    Return autocomplete suggestions for a partial search query.
    The query is tokenized, cleaned, and matched against a Neo4j fulltext
    index on RicgraphNode.value.

    Parameters
    - request: AutocompleteRequest -- pydantic model with `query` and `limit`.

    Returns
    - A list of dicts with keys: id, displayName, type, bestScore.
      Returns an empty list when the query is too short or has no tokens.
    """
    # Validate & clean input
    user_query = (request.query or "").strip()
    if len(user_query) < 2:
        return []

    # Tokenization alignment: the fulltext index analyzer splits on
    # punctuation, so we do the same to ensure each keyword maps to an
    # indexed token.
    user_query = re.sub(r'[^\w\s]', ' ', user_query)

    # Create tokens (all lowercase, remove empty tokens)
    keywords = [
        keyword.lower()
        for keyword in user_query.split()
        if keyword.strip()
    ]

    if not keywords:
        return []

    clean_query = " ".join(keywords)
    lucene_query = build_lucene_query(keywords)

    try:
        rows = graph.execute_query(
            AUTOCOMPLETE_CYPHER,
            result_transformer_=Result.data,
            indexName=FULLTEXT_INDEX_NAME,
            luceneQuery=lucene_query,
            keywords=keywords,
            firstKeyword=keywords[0],
            cleanQuery=clean_query,
            limit=request.limit,
        )
    except Exception as e:
        print(f"[ricgraph_queries] Autocomplete query failed for '{request.query}': {e}")
        raise HTTPException(status_code=500, detail="Autocomplete query failed")

    return rows
