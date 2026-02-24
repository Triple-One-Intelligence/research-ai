import re

from app.utils.ricgraph.RicgraphAPI import execute_query
from app.utils.schemas import Suggestions


def autocomplete(user_query: str, limit: int = 10) -> Suggestions:
    """
    Autocomplete search function for Neo4j.
    """

    # Input Validation
    user_query = (user_query or "").strip()
    if len(user_query) < 2:
        return Suggestions(persons=[], organizations=[])

    # Input Cleaning
    # Allow Unicode letters/numbers (\w), allow whitespace (\s).
    # Replace everything else (hyphens, apostrophes, punctuation) with space.
    user_query = re.sub(r'[^\w\s]', ' ', user_query)

    # Create tokens (all lowercase, remove empyt tokens)
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

    cypher_query = """
            CALL () {
                // Persons
                // Explicitly use the category index if it exists
                MATCH (p:RicgraphNode)
                WHERE p.category = 'person'
                AND ALL(word IN split($cleanQuery, ' ') WHERE toLower(coalesce(p.value, '')) CONTAINS word)

                // Sort by length first before cutting.
                // Shorter names are more likely exact matches.
                WITH p
                ORDER BY size(p.value) ASC
                LIMIT 500

                // Data cleaning (uuid + leading comma)
                WITH p, trim(split(p.value, '#')[0]) AS rawClean
                WITH p, CASE WHEN rawClean STARTS WITH ',' THEN trim(substring(rawClean, 1)) ELSE rawClean END AS name

                // Clean the DB name as well for comparison
                WITH p, name,
                     toLower(reduce(s = name, char IN [',','.','-'] | replace(s, char, ' '))) AS dbCleanName

                WITH p, name,
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

                RETURN p._key AS id, name, 'person' AS type, matchScore, formatScore

                UNION ALL

                // Organizations
                MATCH (o:RicgraphNode)
                WHERE o.category = 'organization'
                AND ALL(word IN split($cleanQuery, ' ') WHERE toLower(coalesce(o.value, '')) CONTAINS word)

                WITH o
                ORDER BY size(o.value) ASC
                LIMIT 500

                WITH o, trim(split(o.value, '#')[0]) AS rawClean
                WITH o, CASE WHEN rawClean STARTS WITH ',' THEN trim(substring(rawClean, 1)) ELSE rawClean END AS name

                WITH o, name,
                     toLower(reduce(s = name, char IN [',','.','-'] | replace(s, char, ' '))) AS dbCleanName

                WITH o, name,
                     CASE
                        WHEN dbCleanName = $cleanQuery THEN 100 // Fix point 3
                        WHEN toLower(name) STARTS WITH $firstKeyword THEN 50
                        ELSE 10
                     END AS matchScore,
                     CASE
                        WHEN name CONTAINS ',' THEN 3
                        WHEN name CONTAINS ' ' THEN 2
                        ELSE 1
                     END AS formatScore

                RETURN o._key AS id, name, 'organization' AS type, matchScore, formatScore
            }

            WITH id, name, type, matchScore, formatScore
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
        firstKeyword=keywords[0],
        cleanQuery=clean_query,
        limit=limit
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
