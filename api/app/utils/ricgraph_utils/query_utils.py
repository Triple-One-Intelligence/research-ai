import os
import re
from neo4j import Driver, GraphDatabase

REMOTE_NEO4J_URL  = os.environ["REMOTE_NEO4J_URL"]
REMOTE_NEO4J_USER = os.environ["REMOTE_NEO4J_USER"]
REMOTE_NEO4J_PASS = os.environ["REMOTE_NEO4J_PASS"]
FULLTEXT_INDEX_NAME = "ValueFulltextIndex"

graph = None # the graph database driver instance will live here once connect_to_database is called

def connect_to_database() -> None:
    """Connect to the Neo4j graph database of ricgraph and return the driver instance."""
    driver = GraphDatabase.driver(REMOTE_NEO4J_URL, auth=(REMOTE_NEO4J_USER, REMOTE_NEO4J_PASS))
    driver.verify_connectivity()

    global graph
    graph = driver

def ensure_fulltext_indexes(driver: Driver) -> None:
    """Create the fulltext index if it doesn't already exist."""
    with driver.session() as session:
        result = session.run(
            "SHOW FULLTEXT INDEXES YIELD name WHERE name = $name RETURN name",
            name=FULLTEXT_INDEX_NAME,
        )
        if not result.single():
            session.run(
                f"CREATE FULLTEXT INDEX {FULLTEXT_INDEX_NAME} "
                f"FOR (n:RicgraphNode) ON EACH [n.value]"
            )
            print(f"[query_utils] Created fulltext index '{FULLTEXT_INDEX_NAME}'.")

        session.run(
            "CALL db.awaitIndex($name)",
            name=FULLTEXT_INDEX_NAME,
        )
        print(f"[query_utils] Fulltext index '{FULLTEXT_INDEX_NAME}' is online.")

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


# Tokenization alignment: the fulltext index analyzer splits on
# punctuation, so we do the same to ensure each keyword maps to an
# indexed token.
def normalize_query_for_index(user_query: str):
    return re.sub(r'[^\w\s]', ' ', user_query)
