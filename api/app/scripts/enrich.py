"""
Enrichment script: fetches abstracts from OpenAlex and stores them with
vector embeddings on Neo4j publication nodes.

Run inside the API container:
    python -m app.scripts.enrich [--force] [--batch-size N]
"""

import argparse
import logging
import os
import sys
import time

import httpx
import app.utils.database_utils.database_utils as database_utils
# Refactoring: Shotgun Surgery fix — imports from centralized config in ai_utils
from app.utils.ai_utils.ai_utils import AI_SERVICE_URL, EMBED_MODEL, EMBED_DIMENSIONS, EMBED_NUM_GPU

log = logging.getLogger(__name__)

OPENALEX_MAILTO = os.getenv("OPENALEX_MAILTO", "")


# ── OpenAlex ────────────────────────────────────────────────────────────────

def reconstruct_abstract(inverted_index: dict) -> str:
    """Reconstruct plain-text abstract from OpenAlex inverted index format."""
    if not inverted_index:
        return ""
    word_positions = []
    for word, positions in inverted_index.items():
        for pos in positions:
            word_positions.append((pos, word))
    word_positions.sort()
    return " ".join(w for _, w in word_positions)


def fetch_abstract(doi: str, client: httpx.Client) -> str | None:
    """Fetch abstract for a DOI from the OpenAlex API."""
    url = f"https://api.openalex.org/works/doi:{doi}"
    params = {}
    if OPENALEX_MAILTO:
        params["mailto"] = OPENALEX_MAILTO

    try:
        resp = client.get(url, params=params, timeout=15.0)
        if resp.status_code == 404:
            log.warning("Could not find the given DOI: %s", doi)
            return None
        resp.raise_for_status()
        data = resp.json()

        # Try abstract_inverted_index first (most common)
        inv_idx = data.get("abstract_inverted_index")
        if inv_idx:
            return reconstruct_abstract(inv_idx)

        log.warning("Abstract was not in the inverted index format, DOI: %s", doi)
        return None
    except httpx.HTTPError as e:
        log.error("Error fetching %s: %s", doi, e)
        return None


def generate_embedding(text: str, client: httpx.Client) -> list[float] | None:
    """Generate an embedding vector via Ollama."""
    try:
        # Try the newer /api/embed endpoint first (Ollama >=0.15)
        resp = client.post(
            f"{AI_SERVICE_URL}/api/embed",
            json={"model": EMBED_MODEL, "input": text},
            timeout=60.0,
        )
        if resp.status_code == 404:
            # Fall back to legacy /api/embeddings endpoint
            resp = client.post(
                f"{AI_SERVICE_URL}/api/embeddings",
                json={"model": EMBED_MODEL, "prompt": text},
                timeout=60.0,
            )
            resp.raise_for_status()
            return resp.json().get("embedding")
        resp.raise_for_status()
        data = resp.json()
        # /api/embed returns {"embeddings": [[...]]}
        embeddings = data.get("embeddings")
        if embeddings and len(embeddings) > 0:
            return embeddings[0]
        return None
    except httpx.HTTPError as e:
        log.error("Embedding error: %s", e)
        return None


# ── Main enrichment loop ───────────────────────────────────────────────────

# Refactoring: Duplicate Code fix — was two near-identical Cypher queries
def find_publication_dois(driver, force: bool) -> list[str]:
    """Return DOIs for publication nodes that need enrichment."""
    base = "MATCH (n:RicgraphNode) WHERE n.name = 'DOI' AND n.value IS NOT NULL"
    condition = "" if force else " AND n.abstract IS NULL"
    query = f"{base}{condition} RETURN n.value AS doi"
    with driver.session() as session:
        return [r["doi"] for r in session.run(query)]


# Refactoring: Separate Query from Modifier — this only writes, find_publication_dois only reads.
def store_enrichment(driver, doi: str, abstract: str, embedding: list[float]):
    """Write abstract + embedding back to the node."""
    with driver.session() as session:
        session.run(
            "MATCH (n:RicgraphNode {name: 'DOI', value: $doi}) "
            "SET n.abstract = $abstract, n.embedding = $embedding",
            doi=doi,
            abstract=abstract,
            embedding=embedding,
        )


def run(force: bool = False, batch_size: int = 50):
    if not AI_SERVICE_URL:
        log.error("AI_SERVICE_URL env var must be set.")
        sys.exit(1)

    database_utils.connect_to_database()
    driver = database_utils.get_graph()
    try:
        database_utils.ensure_vector_index(driver, EMBED_DIMENSIONS)

        dois = find_publication_dois(driver, force)
        total = len(dois)
        if total == 0:
            log.info("No publications to enrich. Done.")
            return

        log.info("Found %d publication(s) to enrich.", total)
        enriched = 0
        skipped = 0

        with httpx.Client() as client:
            for i, doi in enumerate(dois, 1):
                log.info("[%d/%d] %s", i, total, doi)

                abstract = fetch_abstract(doi, client)
                if not abstract:
                    log.info("No abstract found, skipping.")
                    skipped += 1
                    continue

                embedding = generate_embedding(abstract, client)
                if not embedding:
                    log.warning("Embedding failed, skipping.")
                    skipped += 1
                    continue

                store_enrichment(driver, doi, abstract, embedding)
                enriched += 1
                log.info("OK (%d chars, %dd vector)", len(abstract), len(embedding))

                # Be polite to OpenAlex (they ask for <10 req/s)
                time.sleep(0.15)
                if i % batch_size == 0:
                    log.info("Processed %d/%d, pausing briefly...", i, total)
                    time.sleep(1)

        log.info("Done. Enriched: %d, Skipped: %d, Total: %d", enriched, skipped, total)
    finally:
        driver.close()


# ── CLI ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Enrich Neo4j publication nodes with abstracts and embeddings."
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Re-enrich all publications, even those that already have abstracts.",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=50,
        help="Pause briefly every N items (default: 50).",
    )
    args = parser.parse_args()
    run(force=args.force, batch_size=args.batch_size)


if __name__ == "__main__":
    main()
