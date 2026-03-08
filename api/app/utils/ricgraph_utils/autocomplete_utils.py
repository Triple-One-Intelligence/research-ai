from app.utils.database_utils import query_utils, database_utils
from neo4j import Result
from app.utils.schemas import Suggestions, Person, Organization

AUTOCOMPLETE_CYPHER = """
    CALL db.index.fulltext.queryNodes($indexName, $luceneQuery)
    YIELD node, score
    WHERE node.name IN ['FULL_NAME', 'FULL_NAME_ASCII', 'ORGANIZATION_NAME']
    OPTIONAL MATCH (root {name: 'person-root'})--(node)
    
    // find the target/root node (for orgs just the name node, but for persons the root node)
    WITH node, score,
    CASE node.category 
        WHEN 'person' THEN root
        ELSE node
    END AS target
    ORDER BY score DESC
    LIMIT 200    // limit number of results to a manageable 200
    
    // (implicitly) sorts by target, makes a list out of all nodes which share a root and gets the first
    // also takes the best score among these variants
    WITH target,
        head(collect(node)) AS bestNode,
        max(score) AS bestScore

    // Data cleaning (uuid + leading comma)
    WITH target, bestNode, bestScore, trim(split(bestNode.value, '#')[0]) AS rawClean
    WITH target, bestScore, CASE WHEN rawClean STARTS WITH ',' THEN trim(substring(rawClean, 1)) ELSE rawClean END AS name

    // find the id
    WITH target, name, bestScore, target.value AS id, target.category AS type

    RETURN id, name, bestScore, type
    ORDER BY bestScore DESC, name ASC
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

    # Tokenization alignment
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

    rows = database_utils.get_graph().execute_query(
        AUTOCOMPLETE_CYPHER,
        result_transformer_=Result.data,
        indexName=database_utils.FULLTEXT_INDEX_NAME,
        luceneQuery=lucene_query,
        limit=limit,
    )

    for row in rows:
        if row.get("type") == "person":
            persons_out.append( Person(author_id=row["id"], name=row["name"]))
        elif row.get("type") == "organization":
            orgs_out.append( Organization(organization_id= row["id"],name= row["name"]))

    return Suggestions(persons=persons_out, organizations=orgs_out)
