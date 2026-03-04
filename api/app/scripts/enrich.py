"""
Enrichment script: fetches abstracts from OpenAlex and stores them with
vector embeddings on Neo4j publication nodes.

Run inside the API container:
    python -m app.scripts.enrich [--force] [--batch-size N]
"""

import argparse
import os
import re
import sys
import time

import httpx
from neo4j import GraphDatabase

# ── Configuration from environment ──────────────────────────────────────────

NEO4J_URL = os.getenv("REMOTE_NEO4J_URL")
NEO4J_USER = os.getenv("REMOTE_NEO4J_USER")
NEO4J_PASS = os.getenv("REMOTE_NEO4J_PASS")
AI_SERVICE_URL = os.getenv("AI_SERVICE_URL")

EMBED_MODEL = os.getenv("EMBED_MODEL", "nomic-embed-text")
EMBED_DIMENSIONS = int(os.getenv("EMBED_DIMENSIONS", "768"))
OPENALEX_MAILTO = os.getenv("OPENALEX_MAILTO", "")

VECTOR_INDEX_NAME = "publicationEmbeddingIndex"

# Validate index name to prevent Cypher injection in DDL statements
if not re.fullmatch(r'[A-Za-z_]\w*', VECTOR_INDEX_NAME):
    raise ValueError(f"Invalid index name: {VECTOR_INDEX_NAME!r}")


def get_driver():
    if not all([NEO4J_URL, NEO4J_USER, NEO4J_PASS]):
        print("[enrich] ERROR: REMOTE_NEO4J_URL/USER/PASS env vars must be set.")
        sys.exit(1)
    driver = GraphDatabase.driver(NEO4J_URL, auth=(NEO4J_USER, NEO4J_PASS))
    driver.verify_connectivity()
    print(f"[enrich] Connected to Neo4j at {NEO4J_URL}")
    return driver


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
            return None
        resp.raise_for_status()
        data = resp.json()

        # Try abstract_inverted_index first (most common)
        inv_idx = data.get("abstract_inverted_index")
        if inv_idx:
            return reconstruct_abstract(inv_idx)

        return None
    except httpx.HTTPError as e:
        print(f"  [openalex] Error fetching {doi}: {e}")
        return None


# ── Ollama embeddings ───────────────────────────────────────────────────────

def generate_embedding(text: str, client: httpx.Client) -> list[float] | None:
    """Generate an embedding vector via Ollama."""
    url = f"{AI_SERVICE_URL}/api/embeddings"
    try:
        resp = client.post(
            url,
            json={"model": EMBED_MODEL, "prompt": text},
            timeout=60.0,
        )
        resp.raise_for_status()
        return resp.json().get("embedding")
    except httpx.HTTPError as e:
        print(f"  [ollama] Embedding error: {e}")
        return None


# ── Neo4j vector index ──────────────────────────────────────────────────────

def ensure_vector_index(driver) -> None:
    """Create or recreate the vector index with the configured dimensions."""
    with driver.session() as session:
        # Check if index exists and has correct dimensions
        result = session.run(
            "SHOW VECTOR INDEXES YIELD name, options "
            "WHERE name = $name RETURN options",
            name=VECTOR_INDEX_NAME,
        )
        record = result.single()

        if record:
            existing_dims = (
                record["options"]
                .get("indexConfig", {})
                .get("vector.dimensions", 0)
            )
            if existing_dims == EMBED_DIMENSIONS:
                print(
                    f"[enrich] Vector index '{VECTOR_INDEX_NAME}' exists "
                    f"with {EMBED_DIMENSIONS} dimensions – OK."
                )
                return
            # Dimensions mismatch – drop and recreate
            print(
                f"[enrich] Dimension mismatch ({existing_dims} vs "
                f"{EMBED_DIMENSIONS}). Recreating index..."
            )
            session.run(f"DROP INDEX {VECTOR_INDEX_NAME}")

        # Create index
        session.run(
            f"CREATE VECTOR INDEX {VECTOR_INDEX_NAME} "
            f"FOR (n:RicgraphNode) ON (n.embedding) "
            f"OPTIONS {{indexConfig: {{"
            f"  `vector.dimensions`: {EMBED_DIMENSIONS},"
            f"  `vector.similarity_function`: 'cosine'"
            f"}}}}"
        )
        print(
            f"[enrich] Created vector index '{VECTOR_INDEX_NAME}' "
            f"({EMBED_DIMENSIONS} dimensions)."
        )


# ── Main enrichment loop ───────────────────────────────────────────────────

def find_publication_dois(driver, force: bool) -> list[str]:
    """Return DOIs for publication nodes that need enrichment."""
    with driver.session() as session:
        if force:
            # All publication DOIs
            result = session.run(
                "MATCH (n:RicgraphNode) "
                "WHERE n.name = 'DOI' AND n.value IS NOT NULL "
                "RETURN n.value AS doi"
            )
        else:
            # Only those missing an abstract
            result = session.run(
                "MATCH (n:RicgraphNode) "
                "WHERE n.name = 'DOI' AND n.value IS NOT NULL "
                "AND n.abstract IS NULL "
                "RETURN n.value AS doi"
            )
        return [r["doi"] for r in result]


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
        print("[enrich] ERROR: AI_SERVICE_URL env var must be set.")
        sys.exit(1)

    driver = get_driver()
    try:
        ensure_vector_index(driver)

        dois = find_publication_dois(driver, force)
        total = len(dois)
        if total == 0:
            print("[enrich] No publications to enrich. Done.")
            return

        print(f"[enrich] Found {total} publication(s) to enrich.")
        enriched = 0
        skipped = 0

        with httpx.Client() as client:
            for i, doi in enumerate(dois, 1):
                print(f"  [{i}/{total}] {doi}")

                abstract = fetch_abstract(doi, client)
                if not abstract:
                    print("    -> No abstract found, skipping.")
                    skipped += 1
                    continue

                embedding = generate_embedding(abstract, client)
                if not embedding:
                    print("    -> Embedding failed, skipping.")
                    skipped += 1
                    continue

                store_enrichment(driver, doi, abstract, embedding)
                enriched += 1
                print(f"    -> OK ({len(abstract)} chars, {len(embedding)}d vector)")

                # Be polite to OpenAlex (they ask for <10 req/s)
                time.sleep(0.15)
                if i % batch_size == 0:
                    print(f"  [batch] Processed {i}/{total}, pausing briefly...")
                    time.sleep(1)

        print(
            f"[enrich] Done. Enriched: {enriched}, Skipped: {skipped}, "
            f"Total: {total}"
        )
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
