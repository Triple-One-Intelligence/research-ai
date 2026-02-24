# this file is used to execute queries directly on the ricgraph database, instead of using the API.

from typing import Any

import uvicorn
from fastapi import FastAPI, HTTPException, Request
from neo4j import Driver, GraphDatabase, Result

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

FULLTEXT_INDEX_NAME = "RicgraphValueFulltext"

def get_graph() -> Driver:
    try:
        graph = GraphDatabase.driver(NEO4J_URI, auth=(USERNAME, PASSWORD))
        graph.verify_connectivity()
    except Exception as e:
        print("open_ricgraph(): An exception occurred. Name: " + type(e).__name__ + ",")
        print("  error message: " + str(e) + ".")
        exit(1)

    return graph

def ensure_fulltext_indexes(driver: Driver) -> None:
    """Create the fulltext index if it doesn't already exist."""
    driver.execute_query(
        f"CREATE FULLTEXT INDEX {FULLTEXT_INDEX_NAME} IF NOT EXISTS "
        f"FOR (n:RicgraphNode) ON EACH [n.value]",
    )

graph = get_graph()
ensure_fulltext_indexes(graph)

# execute_query(
# query,
# parameters_=None,
# routing_=neo4j.RoutingControl.WRITE,
# database_=None,
# impersonated_user_=None,
# bookmark_manager_=self.execute_query_bookmark_manager,
# auth_=None,
# result_transformer_=Result.to_eager_result, **kwargs)


@app.get("/query")
async def executeQuery(request: Request):

    # get the 'query' parameter (the word that needs autocompleting)
    query = request.query_params.get("query")
    if not query:
        raise HTTPException(status_code=400, detail="Missing 'query' parameter")

    # build params dict from remaining query params and allow non-str values
    params: dict[str, Any] = {
        key: value for key, value in request.query_params.items() if key != "query"
    }

    # convert numeric-looking values to int where appropriate
    for key, value in list(params.items()):
        if isinstance(value, str) and value.isdigit():
            params[key] = int(value)

    rows = graph.execute_query(query, result_transformer_=Result.data, **params)
    return rows


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=3030)
