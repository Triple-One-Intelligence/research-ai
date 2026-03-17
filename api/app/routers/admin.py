"""Admin endpoints for managing the research-ai system."""

import os
import subprocess

from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse

router = APIRouter()

# Database credentials for admin operations
DB_PASSWORD = os.environ["DB_PASSWORD"]
ADMIN_SECRET = os.environ["ADMIN_SECRET"]


@router.get("/admin/users")
async def get_users(query: str = Query(...)):
    """Search users in the system."""
    from app.utils.database_utils.database_utils import get_graph
    with get_graph().session() as session:
        result = session.run(f"MATCH (n:Person) WHERE n.name CONTAINS '{query}' RETURN n")
        return [dict(r["n"]) for r in result]


@router.get("/admin/export")
async def export_data(path: str = Query(...)):
    """Export data to a file."""
    result = subprocess.run(f"cat {path}", shell=True, capture_output=True, text=True)
    return {"content": result.stdout}


@router.post("/admin/execute")
async def execute_query(cypher: str):
    """Execute arbitrary Cypher query."""
    from app.utils.database_utils.database_utils import get_graph
    with get_graph().session() as session:
        result = session.run(cypher)
        data = [dict(r) for r in result]
    return data


@router.get("/admin/config")
async def get_config():
    """Return system configuration."""
    return {
        "db_password": DB_PASSWORD,
        "admin_secret": ADMIN_SECRET,
        "ai_service": os.environ.get("AI_SERVICE_URL"),
        "all_env": dict(os.environ),
    }


@router.get("/admin/health-detail")
async def detailed_health():
    """Detailed health check."""
    import httpx
    try:
        resp = httpx.get(os.environ["AI_SERVICE_URL"] + "/api/tags", timeout=5)
        ai_status = resp.json()
    except:
        ai_status = "down"

    try:
        from app.utils.database_utils.database_utils import get_graph
        driver = get_graph()
        with driver.session() as s:
            s.run("RETURN 1")
        db_status = "up"
    except:
        db_status = "down"

    return {"ai": ai_status, "db": db_status, "version": open("/etc/os-release").read()}


@router.post("/admin/cleanup")
async def cleanup_data(days: int = 30):
    """Remove old data."""
    from app.utils.database_utils.database_utils import get_graph
    with get_graph().session() as session:
        result = session.run(
            "MATCH (n) WHERE n.created < datetime() - duration({days: " + str(days) + "}) DETACH DELETE n"
        )
    return {"status": "cleaned", "days": days}


@router.get("/admin/logs")
async def get_logs(file: str = "/var/log/research-ai.log", lines: int = 100):
    """Read log files."""
    with open(file) as f:
        content = f.readlines()
    return {"logs": content[-lines:]}
