"""
Ricgraph Query API.

This module exposes a FastAPI app for executing arbitrary Cypher queries
against the local Neo4j instance used by ricgraph.

Endpoint
- POST /query
  - query: str (required)  -- the Cypher query string to execute
  - params: dict (optional)  -- parameters forwarded to the Neo4j driver's
    `execute_query` call (for example: parameter maps, database selection,
    transformers)
  - response: list[dict]  -- rows returned by the query, serialized via
    `neo4j.Result.data()`
"""
from typing import Any
import uvicorn
from fastapi import FastAPI, HTTPException
from typing import cast, LiteralString
from neo4j import Driver, GraphDatabase, Result
from pydantic import BaseModel

app = FastAPI(
    title="Ricgraph Query API",
    description="API for custom ricgraph queries",
    version="1.0.0",
    root_path="/api",
    debug=True,
)

# Credentials are hardcoded for now, this needs to be changed to use environment variables
NEO4J_URI = "bolt://localhost:7687"
USERNAME = "neo4j"
PASSWORD = "dSRj5ewlbDR4"

FULLTEXT_INDEX_NAME = "ValueFulltextIndex"

def get_graph() -> Driver:
    """Connect to the Neo4j graph database of ricgraph and return the driver instance."""
    try:
        graph = GraphDatabase.driver(NEO4J_URI, auth=(USERNAME, PASSWORD))
        graph.verify_connectivity()
    except Exception as e:
        print("get_graph(): An exception occurred. Name: " + type(e).__name__ + ",")
        print("  error message: " + str(e) + ".")
        exit(1)

    return graph

def ensure_fulltext_indexes(driver: Driver) -> None:
    """Create the fulltext index if it doesn't already exist."""
    with driver.session() as session:
        # Check if the index already exists
        result = session.run(
            "SHOW FULLTEXT INDEXES YIELD name WHERE name = $name RETURN name",
            name=FULLTEXT_INDEX_NAME,
        )
        if not result.single():
            # Index does not exist yet, create it
            session.run(
                f"CREATE FULLTEXT INDEX {FULLTEXT_INDEX_NAME} "
                f"FOR (n:RicgraphNode) ON EACH [n.value]"
            )
            print(f"Created fulltext index '{FULLTEXT_INDEX_NAME}'.")

        # Wait until the index is online before proceeding
        session.run(
            "CALL db.awaitIndex($name)",
            name=FULLTEXT_INDEX_NAME,
        )
        print(f"Fulltext index '{FULLTEXT_INDEX_NAME}' is online.")

graph = get_graph()
ensure_fulltext_indexes(graph)

class QueryRequest(BaseModel):
    """
    Incoming request model for the /query endpoint.

    Parameters
    - query: str (required)  -- Cypher query string to execute
    - params: dict (optional)  -- keyword args forwarded to the Neo4j driver's
      `execute_query` call (for example: `parameters_`, `database_`, `result_transformer_`).
    """
    query: str
    params: dict[str, Any] = {}

@app.post("/query")
async def executeQuery(request: QueryRequest):
    """
    Endpoint POST /query

    Execute a raw Cypher query against the configured Neo4j instance and return
    the query results.

    Parameters
    - request: QueryRequest  -- pydantic model containing `query` and optional
      `params` forwarded to the driver.

    Returns
    - A list of rows (each row represented as a dict) as produced by
      `neo4j.Result.data()`.
    """
    if not request.query:
        raise HTTPException(status_code=400, detail="Missing 'query' field")

    rows = graph.execute_query(cast(LiteralString, request.query), result_transformer_=Result.data, **request.params)
    return rows

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=3030)
