import os
from datetime import datetime
import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.ai import router as ai_router
from app.routers import connections, autocomplete

from contextlib import asynccontextmanager
import app.utils.ricgraph_utils.query_utils as query_utils

# responsible for start up and shut down tasks
@asynccontextmanager
async def lifespan(app: FastAPI):
    print("Starting API...")
    # connect directly to ricgraph neo4j database for custom queries
    try:
        query_utils.connect_to_database()
    except Exception as e:
        print(f"couldn't connect to ricgraph database: {e}")
        query_utils.graph.close()
        raise  # indicate that startup failed
    print("connected to ricgraph database")
    query_utils.ensure_fulltext_indexes(query_utils.graph)
    print("API start up complete")

    yield

    print("Shutting down API...")
    query_utils.graph.close()
    print("disconnected from ricgraph database")
    print("API shut down complete")


app = FastAPI(
    title="Research AI API",
    description="API",
    version="0.0.1",
    root_path="/api",
    debug=True,
    lifespan=lifespan
)

cors_env = os.environ.get("CORS_ORIGINS", "http://localhost:5173,http://localhost:3000")
origins = [o.strip() for o in cors_env.split(",")]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(connections.router)
app.include_router(autocomplete.router)
app.include_router(ai_router)

memory_db = {"fruits": []}

@app.get("/health")
def health():
    return {
        "status": "ok",
        "service": "Research-AI API",
        "time": datetime.now().isoformat()
    }

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
