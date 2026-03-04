import app.utils.ricgraph_utils.query_utils as query_utils
from neo4j import Result
from app.utils.schemas import Suggestions, Person, Organization

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

def autocomplete(user_query: str, limit: int = 10) -> Suggestions:
    """
    Return autocomplete suggestions for a partial search query.
    The query is tokenized, cleaned, and matched against a Neo4j fulltext
    index on RicgraphNode.value.
    """

    persons_out : list[Person]       = []
    orgs_out    : list[Organization] = []

    # Validate & clean input
    query = (user_query or "").strip()
    if len(query) < 2:
        return Suggestions(persons=persons_out, organizations=orgs_out)

    # Tokenization alignment: the fulltext index analyzer splits on
    # punctuation, so we do the same to ensure each keyword maps to an
    # indexed token.
    query = query_utils.normalize_query_for_index(query)

    # Create tokens (all lowercase, remove empty tokens)
    keywords = [
        keyword.lower()
        for keyword in query.split()
        if keyword.strip()
    ]

    if not keywords:
        return Suggestions(persons=persons_out, organizations=orgs_out)

    clean_query = " ".join(keywords)
    lucene_query = query_utils.build_lucene_query(keywords)

    rows = query_utils.get_graph().execute_query(
        AUTOCOMPLETE_CYPHER,
        result_transformer_=Result.data,
        indexName=query_utils.FULLTEXT_INDEX_NAME,
        luceneQuery=lucene_query,
        keywords=keywords,
        firstKeyword=keywords[0],
        cleanQuery=clean_query,
        limit=limit,
    )

    for row in rows:
        if row.get("type") == "person":
            persons_out.append( Person(author_id=row["id"], name=row["displayName"]))
        elif row.get("type") == "organization":
            orgs_out.append( Organization(organization_id= row["id"],name= row["displayName"]))

    return Suggestions(persons=persons_out, organizations=orgs_out)
