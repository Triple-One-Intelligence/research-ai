import logging

from neo4j.exceptions import ServiceUnavailable

from app.utils.database_utils import query_utils, database_utils
from app.utils.schemas import Suggestions, Person, Organization
from app.utils.ricgraph_utils.queries.autocomplete_queries import AUTOCOMPLETE_CYPHER

log = logging.getLogger(__name__)

class AutocompleteError(RuntimeError):
    pass

class InvalidQueryError(ValueError):
    pass

def get_autocomplete_suggestions(user_query: str, limit: int = 10) -> Suggestions:
    """
    Return autocomplete suggestions for a partial search query.
    The query is tokenized, cleaned, and matched against a Neo4j fulltext
    index on RicgraphNode.value.
    """

    persons_out: list[Person] = []
    orgs_out: list[Organization] = []

    # Validate & clean input
    query = (user_query or "").strip()
    if len(query) < 2:
        raise InvalidQueryError("Query must be at least 2 characters long.")

    # Tokenization alignment
    query = query_utils.normalize_query_for_index(query)

    # Create tokens (all lowercase, remove empty tokens)
    keywords = [keyword.lower() for keyword in query.split() if keyword.strip()]

    if not keywords:
        return Suggestions(persons=persons_out, organizations=orgs_out)

    clean_query = " ".join(keywords)
    lucene_query = query_utils.build_lucene_query(keywords)

    try:
        rows = database_utils.execute_cypher(
            AUTOCOMPLETE_CYPHER,
            indexName=database_utils.FULLTEXT_INDEX_NAME,
            luceneQuery=lucene_query,
            keywords=keywords,
            firstKeyword=keywords[0],
            cleanQuery=clean_query,
            limit=limit,
        )

        for row in rows:
            if row.get("type") == "person":
                persons_out.append(Person(author_id=row["id"], name=row["displayName"]))
            elif row.get("type") == "organization":
                orgs_out.append(Organization(organization_id=row["id"], name=row["displayName"]))
            else:
                raise AutocompleteError(f"Unexpected type: {row.get('type')!r}")

    except ServiceUnavailable:
        # Propagate Neo4j service availability issues so the API layer can return 503.
        raise
    except RuntimeError:
        # Propagate driver-not-initialized errors so the API layer can return 503.
        raise
    except Exception as exception:
        log.error("Autocomplete query failed for query=%r", query)
        raise AutocompleteError("Autocomplete query failed") from exception

    return Suggestions(persons=persons_out, organizations=orgs_out)
