#!/bin/sh
set -eu

SCRIPT=/app/ricgraph/ricgraph-queries.py
INI=/app/ricgraph/ricgraph.ini

neo4j start

# Copy ini file to the right directory
if [ -f "$INI" ]; then
  echo "[ricgraph-entrypoint] Copying $INI"
  cp "$INI" /usr/ricgraph.ini || {
    echo "[ricgraph-entrypoint] Failed to copy $INI" >&2
    exit 1
  }
else
  echo "[ricgraph-entrypoint] $SCRIPT not present, skipping"
fi

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
