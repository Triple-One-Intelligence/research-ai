#!/bin/sh
set -eu

REQ=/app/ricgraph/requirements.txt
SCRIPT=/app/ricgraph/ricgraph-queries.py
INI=/app/ricgraph/ricgraph.ini

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

# Install Python requirements
if [ -f "$REQ" ]; then
  echo "[ricgraph-entrypoint] Installing Python requirements from $REQ"
  python -m pip install --no-cache-dir -r "$REQ" || {
    echo "[ricgraph-entrypoint] pip install failed" >&2
    exit 1
  }
else
  echo "[ricgraph-entrypoint] No requirements.txt found at $REQ, skipping pip install"
fi

# Run the queries script
if [ -f "$SCRIPT" ]; then
  echo "[ricgraph-entrypoint] Running $SCRIPT"
  python "$SCRIPT" || echo "[ricgraph-entrypoint] $SCRIPT returned non-zero exit code"
else
  echo "[ricgraph-entrypoint] $SCRIPT not present, skipping"
fi

# Exec base image CMD
exec "$@"
