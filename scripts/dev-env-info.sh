#!/usr/bin/env bash
# Print dev environment connection info for developers.
# Run on the production server after `make deploy`.
set -euo pipefail

G='\033[32m' C='\033[36m' B='\033[1m' R='\033[0m'

SERVER_IP=$(hostname -I 2>/dev/null | awk '{print $1}')
SERVER_HOST=$(hostname -f 2>/dev/null || hostname)
PROD_ENV="/etc/research-ai/research-ai-prod.env"

_env() { grep -s "^$1=" "$PROD_ENV" 2>/dev/null | cut -d= -f2- || echo "$2"; }

CADDY_HOST=$(_env CADDY_HOSTNAME "$SERVER_HOST")
NEO4J_USER=$(_env REMOTE_NEO4J_USER "neo4j")
NEO4J_PASS=$(_env REMOTE_NEO4J_PASS "CHANGE_ME")

printf "\n${B}═══ Dev Environment Connection Info ═══${R}\n\n"
printf "Copy the following into your ${C}kube/research-ai-dev.env${R} file.\n\n"
printf "${C}--- cut here ---${R}\n"

cat <<EOF
# Dev env — auto-generated from $SERVER_HOST ($SERVER_IP)
# Generated: $(date -Iseconds)

# --- FRONTEND ---
VITE_API_URL=/api

# --- SSH TUNNEL ---
# Dev pod connects to prod via SSH tunnel.
# Verify: ssh root@$SERVER_IP echo ok
REMOTE_SERVER=root@$SERVER_IP

# --- API SECRETS (local dev only) ---
JWT_SECRET=local_dev_secret
SERVER_AUTH_USER=devuser
SERVER_AUTH_PASS=devpass

# --- REMOTE SERVICE URLs (via SSH tunnel -> localhost) ---
REMOTE_NEO4J_URL=bolt://localhost:7687
REMOTE_NEO4J_USER=$NEO4J_USER
REMOTE_NEO4J_PASS=$NEO4J_PASS

RICGRAPH_URL=http://localhost:18080
AI_SERVICE_URL=http://localhost:11434

# --- EMBEDDINGS ---
EMBED_MODEL=nomic-embed-text
EMBED_DIMENSIONS=768
OPENALEX_MAILTO=
EOF

printf "${C}--- cut here ---${R}\n\n"

printf "${B}SSH tunnel ports:${R}\n"
echo "  7687  -> Neo4j Bolt   (bolt://localhost:7687)"
echo "  7474  -> Neo4j HTTP   (http://localhost:7474)"
echo "  18080 -> Ricgraph     (http://localhost:18080)"
echo "  3030  -> Ricgraph UI  (http://localhost:3030)"
echo "  11434 -> Ollama       (http://localhost:11434)"
echo ""

printf "${B}Production endpoints:${R}\n"
echo "  HTTPS: https://$CADDY_HOST"
echo "  HTTP:  http://$CADDY_HOST (redirects to HTTPS)"
echo "  API:   https://$CADDY_HOST/api/health"
echo ""

printf "${B}Quick start:${R}\n"
echo "  1. Save the above as kube/research-ai-dev.env"
echo "  2. Verify SSH:  ssh root@$SERVER_IP echo ok"
echo "  3. Start dev:   make dev"
echo "  4. Open:        https://localhost:3000"
echo ""
