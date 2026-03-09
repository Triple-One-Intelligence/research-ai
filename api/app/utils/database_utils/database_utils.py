"""
This file is responsible for establishing a connection to the (remote) neo4j database which
contains both ricgraph and embedding data. Also included are some helper functions which setup some
parts of the database.
"""

import os
import re
import time
from neo4j import Driver, GraphDatabase

REMOTE_NEO4J_URL  = os.environ["REMOTE_NEO4J_URL"]
REMOTE_NEO4J_USER = os.environ["REMOTE_NEO4J_USER"]
REMOTE_NEO4J_PASS = os.environ["REMOTE_NEO4J_PASS"]

FULLTEXT_INDEX_NAME = "ValueFulltextIndex"
VECTOR_INDEX_NAME = "publicationEmbeddingIndex"

def validate_index(index_name : str) -> None:
    """Validate index name to prevent Cypher injection in DDL statements."""
    if not re.fullmatch(r'[A-Za-z_]\w*', index_name):
        raise ValueError(f"Invalid index name: {index_name!r}")

validate_index(FULLTEXT_INDEX_NAME)
validate_index(VECTOR_INDEX_NAME)

graph: Driver | None = None

def connect_to_database(max_retries: int = 10, retry_delay: float = 3.0) -> None:
    """Connect to the Neo4j graph database of ricgraph and return the driver instance."""
    for attempt in range(1, max_retries + 1):
        try:
            driver = GraphDatabase.driver(REMOTE_NEO4J_URL, auth=(REMOTE_NEO4J_USER, REMOTE_NEO4J_PASS))
            driver.verify_connectivity()

            global graph
            graph = driver
            return
        except Exception as e:
            if attempt == max_retries:
                raise
            print(f"[database_utils] Attempt {attempt}/{max_retries} failed: {e}")
            print(f"[database_utils] Retrying in {retry_delay}s...")
            time.sleep(retry_delay)

def startup() -> None:
    """Connect to the Ricgraph Neo4j database and ensure indexes are ready."""
    try:
        connect_to_database()
    except Exception as e:
        print(f"[database_utils] Couldn't connect to Ricgraph database: {e}")
        if graph is not None:
            graph.close()
        raise

    print("[database_utils] Connected to Ricgraph database.")
    assert graph is not None
    ensure_fulltext_indexes(graph)
    print("[database_utils] Startup complete.")

def get_graph() -> Driver:
    """Return the Neo4j driver, raising a clear error if not yet connected."""
    if graph is None:
        raise RuntimeError("Neo4j driver not initialized — was connect_to_database() called?")
    return graph

def shutdown() -> None:
    """Close the Ricgraph Neo4j database connection."""
    global graph
    if graph is not None:
        graph.close()
        graph = None
    print("[database_utils] Disconnected from Ricgraph database.")

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
            print(f"[database_utils] Created fulltext index '{FULLTEXT_INDEX_NAME}'.")

        session.run(
            "CALL db.awaitIndex($name)",
            name=FULLTEXT_INDEX_NAME,
        )
        print(f"[database_utils] Fulltext index '{FULLTEXT_INDEX_NAME}' is online.")

def ensure_vector_index(driver: Driver, embed_dimensions: int) -> None:
    """Create or recreate the vector index with the configured dimensions."""
    with driver.session() as session:
        # Check if index exists and has correct dimensions
        result = session.run(
            "SHOW VECTOR INDEXES YIELD name, options "
            "WHERE name = $name RETURN options",
            name=VECTOR_INDEX_NAME,
        )
        record = result.single()

        if record:
            existing_dims = (
                record["options"]
                .get("indexConfig", {})
                .get("vector.dimensions", 0)
            )
            if existing_dims == embed_dimensions:
                print(
                    f"[database_utils] Vector index '{VECTOR_INDEX_NAME}' exists "
                    f"with {embed_dimensions} dimensions – OK."
                )
                return
            # Dimensions mismatch – drop and recreate
            print(
                f"[database_utils] Dimension mismatch ({existing_dims} vs "
                f"{embed_dimensions}). Recreating index..."
            )
            session.run(f"DROP INDEX {VECTOR_INDEX_NAME}")

        # Create index
        session.run(
            f"CREATE VECTOR INDEX {VECTOR_INDEX_NAME} "
            f"FOR (n:RicgraphNode) ON (n.embedding) "
            f"OPTIONS {{indexConfig: {{"
            f"  `vector.dimensions`: {embed_dimensions},"
            f"  `vector.similarity_function`: 'cosine'"
            f"}}}}"
        )
        print(
            f"[database_utils] Created vector index '{VECTOR_INDEX_NAME}' "
            f"({embed_dimensions} dimensions)."
        )
