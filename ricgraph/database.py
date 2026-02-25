"""
Shared database module for the Ricgraph Query API.

Holds the Neo4j driver instance and fulltext index setup so that
both the main application and individual routers can import them
without circular dependencies.
"""

import os

from neo4j import Driver, GraphDatabase

RIC_NEO4J_URL = os.getenv("RIC_NEO4J_URL", "")
RIC_NEO4J_USER = os.getenv("RIC_NEO4J_USER", "")
RIC_NEO4J_PASS = os.getenv("RIC_NEO4J_PASS", "")

FULLTEXT_INDEX_NAME = "ValueFulltextIndex"


def get_graph() -> Driver:
    """Connect to the Neo4j graph database of ricgraph and return the driver instance."""
    try:
        driver = GraphDatabase.driver(RIC_NEO4J_URL, auth=(RIC_NEO4J_USER, RIC_NEO4J_PASS))
        driver.verify_connectivity()
    except Exception as e:
        print("[database] get_graph(): An exception occurred. Name: " + type(e).__name__ + ",")
        print("  error message: " + str(e) + ".")
        exit(1)

    return driver


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
            print(f"[database] Created fulltext index '{FULLTEXT_INDEX_NAME}'.")

        session.run(
            "CALL db.awaitIndex($name)",
            name=FULLTEXT_INDEX_NAME,
        )
        print(f"[database] Fulltext index '{FULLTEXT_INDEX_NAME}' is online.")


graph = get_graph()
ensure_fulltext_indexes(graph)