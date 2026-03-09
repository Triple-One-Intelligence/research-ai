from app.utils.database_utils import query_utils, database_utils
from neo4j import Result
from app.utils.schemas import Suggestions, Person, Organization
from app.utils.ricgraph_utils.queries.autocomplete_queries import AUTOCOMPLETE_CYPHER

def get_autocomplete_suggestions(user_query: str, limit: int = 10) -> Suggestions:
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
