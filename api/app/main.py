"""FastAPI application entry point — configures logging, CORS, routers, and lifespan."""

import logging
import os
from contextlib import asynccontextmanager
from datetime import datetime

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routers import ai, autocomplete, connections, prompts
import app.utils.database_utils.database_utils as database_utils

logging.basicConfig(
    level=os.environ.get("LOGLEVEL", "INFO").upper(),
    format="%(levelname)s: %(message)s",
)
log = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    database_utils.startup()
    yield
    database_utils.shutdown()


app = FastAPI(
    title="Research AI API",
    description="API",
    version="0.0.1",
    root_path="/api",
    debug=os.environ.get("LOGLEVEL", "INFO").upper() == "DEBUG",
    lifespan=lifespan
)

cors_env = os.environ.get("CORS_ORIGINS", "http://localhost:5173,https://localhost:3000")
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
app.include_router(ai.router)
app.include_router(prompts.router)

@app.get("/health")
def health():
    return {
        "status": "ok",
        "service": "Research-AI API",
        "time": datetime.now().isoformat()
    }

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
