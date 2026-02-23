#!/bin/sh
set -eu

SCRIPT=/app/ricgraph/ricgraph-queries.py

neo4j start

# Run the queries script
if [ -f "$SCRIPT" ]; then
  echo "[ricgraph-entrypoint] Running $SCRIPT"
  python "$SCRIPT" || echo "[ricgraph-entrypoint] $SCRIPT returned non-zero exit code"
else
  echo "[ricgraph-entrypoint] $SCRIPT not present, skipping"
fi

# Start ricgraph explorer and ricgraph REST API
# bin/gunicorn --chdir /app/ricgraph/ricgraph_explorer --bind 0.0.0.0:3030 --workers 5 --worker-class uvicorn.workers.UvicornWorker ricgraph_explorer:create_ricgraph_explorer_app
# while true; do sleep 60; done
