import re

from app.utils.ricgraph.ricgraph_api import execute_query
from app.utils.schemas import Suggestions

# Must match the index name created in ricgraph_queries.py
FULLTEXT_INDEX_NAME = "ValueFulltextIndex"

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


def autocomplete(user_query: str, limit: int = 10) -> Suggestions:
    """
    Autocomplete search function for Neo4j using a fulltext index.
    """

    # Input Validation
    user_query = (user_query or "").strip()
    if len(user_query) < 2:
        return Suggestions(persons=[], organizations=[])

    # Input Cleaning
    # Tokenization alignment: the fulltext index analyzer splits on punctuation,
    # so we do the same here to ensure each keyword maps to an indexed token.
    user_query = re.sub(r'[^\w\s]', ' ', user_query)

    # Create tokens (all lowercase, remove empty tokens)
    # "Boer  Henk" -> ["boer", "henk"]
    keywords = [
        keyword.lower()
        for keyword in user_query.split()
        if keyword.strip()
    ]

    if not keywords:
        return Suggestions(persons=[], organizations=[])

    # Create a clean string for the exact match score (100 points)
    clean_query = " ".join(keywords)

    # Build the Lucene query with prefix wildcards for autocomplete
    lucene_query = build_lucene_query(keywords)

    cypher_query = """
            CALL db.index.fulltext.queryNodes($indexName, $luceneQuery)
            YIELD node, score AS ftScore
            WHERE node.category IN ['person', 'organization']

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

            RETURN id, displayName, type, bestScore
            ORDER BY bestScore DESC, displayName ASC
            LIMIT $limit
            """

    rows = execute_query(
        cypher_query,
        indexName=FULLTEXT_INDEX_NAME,
        luceneQuery=lucene_query,
        firstKeyword=keywords[0],
        cleanQuery=clean_query,
        limit=limit,
    )

    # Map to Output Schema
    persons_out = []
    orgs_out = []

    for row in rows:
        # row["id"] contains the _key from Neo4j
        # row["displayName"] contains the cleaned name

        if row["type"] == "person":
            persons_out.append({
                "author_id": row["id"],
                "name": row["displayName"]
            })
        elif row["type"] == "organization":
            orgs_out.append({
                "organization_id": row["id"],
                "name": row["displayName"]
            })

    return Suggestions(persons=persons_out, organizations=orgs_out)
