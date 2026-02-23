import uvicorn
from fastapi import FastAPI
from neo4j import Result

import ricgraph as rcg

app = FastAPI(
    title="Ricgraph Query API",
    description="API for custom ricgraph queries",
    version="1.0.0",
    root_path="/api ",
    debug=True,
)

NEO4J_URI = "bolt://localhost:7687"
USERNAME = "neo4j"
PASSWORD = "dSRj5ewlbDR4"
graph = rcg.open_ricgraph()

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
def executeQuery(query: str, **params):
    rows = graph.execute_query(query, result_transformer_=Result.data, **params)
    return rows


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=3030)
