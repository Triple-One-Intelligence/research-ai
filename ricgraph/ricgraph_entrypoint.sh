#!/bin/sh
set -eu

SCRIPT=/app/ricgraph/main.py

# Gracefully stop Neo4j when the container is stopped
cleanup() {
  echo "[ricgraph_entrypoint] Shutting down Neo4j..."
  neo4j stop
}
trap cleanup TERM INT

# Start Neo4j in the background
neo4j start

# Wait until Neo4j is actually accepting connections
echo "[ricgraph_entrypoint] Waiting for Neo4j to become ready..."
until neo4j status 2>/dev/null && python -c "
from neo4j import GraphDatabase
import os
driver = GraphDatabase.driver(
    os.getenv('RIC_NEO4J_URL', 'bolt://localhost:7687'),
    auth=(os.getenv('RIC_NEO4J_USER', 'neo4j'), os.getenv('RIC_NEO4J_PASS', 'neo4j'))
)
driver.verify_connectivity()
driver.close()
" 2>/dev/null; do
  sleep 2
done
echo "[ricgraph_entrypoint] Neo4j is ready."

# Run the queries/API script (foreground — keeps the container alive)
if [ -f "$SCRIPT" ]; then
  echo "[ricgraph_entrypoint] Running $SCRIPT"
  exec python "$SCRIPT"
else
  echo "[ricgraph_entrypoint] $SCRIPT not found, exiting."
  exit 1
fi
