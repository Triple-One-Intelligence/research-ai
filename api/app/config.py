"""All environment variables read in one place."""
import os

# --- Neo4j ---
REMOTE_NEO4J_URL  = os.environ["REMOTE_NEO4J_URL"]
REMOTE_NEO4J_USER = os.environ["REMOTE_NEO4J_USER"]
REMOTE_NEO4J_PASS = os.environ["REMOTE_NEO4J_PASS"]

# --- AI service ---
AI_SERVICE_URL      = os.environ["AI_SERVICE_URL"]
CHAT_MODEL          = os.getenv("CHAT_MODEL", "command-r:35b")
EMBED_MODEL         = os.getenv("EMBED_MODEL", "snowflake-arctic-embed2")
EMBED_DIMENSIONS    = int(os.getenv("EMBED_DIMENSIONS", "1024"))
CHAT_MAX_TOKENS     = int(os.getenv("CHAT_MAX_TOKENS", "2048"))
CHAT_CONTEXT_WINDOW = int(os.getenv("CHAT_CONTEXT_WINDOW", "32768"))  # increase for larger GPU VRAM
EMBED_NUM_GPU       = int(os.getenv("EMBED_NUM_GPU", "0"))  # 0 = CPU-only, keeps GPU free for chat

# --- App ---
LOGLEVEL     = os.getenv("LOGLEVEL", "INFO").upper()
CORS_ORIGINS = [o.strip() for o in os.getenv("CORS_ORIGINS", "http://localhost:5173,https://localhost:3000").split(",")]
