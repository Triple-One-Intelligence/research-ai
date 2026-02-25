"""
Ricgraph Query API.

This module exposes a FastAPI app with dedicated endpoints for querying
the local Neo4j instance used by ricgraph. No arbitrary Cypher queries
are accepted — each use-case has its own validated endpoint.

Endpoints
- POST /autocomplete
  - query: str (required)  -- the partial text to autocomplete
  - limit: int (optional, default 10, range 1-100)
  - response: list[dict]  -- matching rows with id, displayName, type, bestScore
"""

import uvicorn
from fastapi import FastAPI
from routers import autocomplete

app = FastAPI(
    title="Ricgraph Query API",
    description="API for dedicated ricgraph queries",
    version="1.0.0",
    root_path="/api",
    debug=True,
)

app.include_router(autocomplete.router)

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8080)
