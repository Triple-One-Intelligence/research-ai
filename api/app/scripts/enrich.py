"""
Enrichment script: fetches abstracts from OpenAlex and stores them with
vector embeddings on Neo4j publication nodes.

Run inside the API container:
    python -m app.scripts.enrich [--force] [--batch-size N]
"""

import argparse
import os
import sys
import time

import httpx
import app.utils.database_utils.database_utils as database_utils
from app.utils.ai_utils.ai_utils import embed


AI_SERVICE_URL = os.environ["AI_SERVICE_URL"]
EMBED_MODEL = os.getenv("EMBED_MODEL", "nomic-embed-text")
EMBED_DIMENSIONS = int(os.getenv("EMBED_DIMENSIONS", "768"))
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
            print(f"  [openalex] Could not find the given DOI: {doi}")
            return None
        resp.raise_for_status()
        data = resp.json()

        # Try abstract_inverted_index first (most common)
        inv_idx = data.get("abstract_inverted_index")
        if inv_idx:
            return reconstruct_abstract(inv_idx)

        print(f"  [openalex] Abstract was not in the inverted index format, DOI: {doi}")
        return None
    except httpx.HTTPError as e:
        print(f"  [openalex] Error fetching {doi}: {e}")
        return None


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

    database_utils.connect_to_database()
    driver = database_utils.get_graph()
    try:
        database_utils.ensure_vector_index(driver, EMBED_DIMENSIONS)

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

                embedding = embed(abstract, client).get("embedding")
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
