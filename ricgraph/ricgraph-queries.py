# this file is used to execute queries directly on the ricgraph database, instead of using the API.

from typing import Any

import uvicorn
from fastapi import FastAPI, HTTPException, Request
from neo4j import Result

import ricgraph as rcg

app = FastAPI(
    title="Ricgraph Query API",
    description="API for custom ricgraph queries",
    version="1.0.0",
    root_path="/api",
    debug=True,
)

NEO4J_URI = "bolt://localhost:7687"
USERNAME = "neo4j"
PASSWORD = "dSRj5ewlbDR4"
graph = rcg.open_ricgraph()

@app.get("/query")
async def executeQuery(request: Request):

    # get the 'query' parameter (the word that needs autocompleting)
    q = request.query_params.get("query")
    if not q:
        raise HTTPException(status_code=400, detail="missing 'query' parameter")

    # build params dict from remaining query params and allow non-str values
    params: dict[str, Any] = {
        k: v for k, v in request.query_params.items() if k != "query"
    }

    # convert numeric-looking values to int where appropriate
    for k, v in list(params.items()):
        if isinstance(v, str) and v.isdigit():
            params[k] = int(v)

    rows = graph.execute_query(q, result_transformer_=Result.data, **params)
    return rows


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=3031)