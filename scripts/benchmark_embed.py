#!/usr/bin/env python3
"""Benchmark embedding models on Ollama using REAL abstracts from Neo4j.

Pulls actual publication abstracts, creates realistic retrieval tests,
measures: recall@1, recall@5, cross-lingual quality, speed.
"""

import json
import math
import random
import time
import sys
import requests

OLLAMA_URL = "http://127.0.0.1:11434"
NEO4J_URL = "http://localhost:7474"

MODELS = [
    {"name": "qwen3-embedding:8b", "dimensions": [1024, 2048, 4096]},
    {"name": "qwen3-embedding:4b", "dimensions": [1024, 2560]},
    {"name": "bge-m3", "dimensions": [1024]},
    {"name": "snowflake-arctic-embed2", "dimensions": [1024]},
    {"name": "nomic-embed-text", "dimensions": [768]},
]

# Number of abstracts to use as the retrieval corpus
CORPUS_SIZE = 200
# Number of query-abstract test pairs to evaluate
NUM_TEST_PAIRS = 20


def neo4j_query(statement: str, params: dict = None):
    """Run a Cypher query via Neo4j HTTP API."""
    # Read credentials from prod env
    import os
    neo4j_pass = os.popen("grep -oP 'NEO4J_AUTH=neo4j/\\K.*' /root/research-ai/kube/research-ai-prod.env").read().strip()
    body = {"statements": [{"statement": statement}]}
    if params:
        body["statements"][0]["parameters"] = params
    resp = requests.post(
        f"{NEO4J_URL}/db/neo4j/tx/commit",
        json=body,
        auth=("neo4j", neo4j_pass),
        timeout=30.0,
    )
    resp.raise_for_status()
    data = resp.json()
    if data.get("errors"):
        raise RuntimeError(f"Neo4j error: {data['errors']}")
    return data["results"][0]["data"]


def fetch_abstracts(limit: int) -> list[dict]:
    """Fetch real abstracts from Neo4j."""
    rows = neo4j_query(
        "MATCH (n:RicgraphNode) WHERE n.name = 'DOI' AND n.abstract IS NOT NULL "
        "AND n.abstract <> '' AND size(n.abstract) > 100 "
        "RETURN n.value AS doi, n.abstract AS abstract, n.comment AS title, "
        "n.category AS category "
        "ORDER BY rand() LIMIT $limit",
        {"limit": limit},
    )
    return [{"doi": r["row"][0], "abstract": r["row"][1], "title": r["row"][2], "category": r["row"][3]} for r in rows]


def generate_queries_from_abstracts(abstracts: list[dict], num_pairs: int) -> list[dict]:
    """Generate realistic search queries from abstract content.

    Strategy: extract key phrases from the abstract to simulate a user
    searching for that publication. Mix of English and Dutch-style queries.
    """
    pairs = []
    selected = random.sample(abstracts, min(num_pairs, len(abstracts)))

    for doc in selected:
        abstract = doc["abstract"]
        title = doc.get("title", "")

        # Strategy 1: Use first ~15 words of abstract as a "topic search"
        words = abstract.split()
        topic_query = " ".join(words[:15])

        # Strategy 2: Use title keywords (if available) - simulates known-item search
        if title and len(title) > 10:
            title_query = title
        else:
            # Use middle chunk of abstract
            mid = len(words) // 2
            title_query = " ".join(words[max(0, mid - 8):mid + 8])

        pairs.append({
            "query": topic_query,
            "query_type": "topic_search",
            "target_doi": doc["doi"],
            "target_abstract": abstract,
        })

    return pairs


def cosine_similarity(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(x * x for x in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


# Models that don't support the 'dimensions' parameter
FIXED_DIM_MODELS = {"bge-m3", "snowflake-arctic-embed2", "nomic-embed-text"}


def embed(text: str, model: str, dimensions: int) -> tuple[list[float], float]:
    """Embed text, return (vector, time_ms). Falls back to legacy endpoint."""
    start = time.perf_counter()
    payload = {"input": text, "model": model}
    if model not in FIXED_DIM_MODELS:
        payload["dimensions"] = dimensions

    resp = requests.post(
        f"{OLLAMA_URL}/api/embed",
        json=payload,
        timeout=120.0,
    )
    if resp.status_code == 500:
        # Fall back to legacy /api/embeddings endpoint
        legacy_payload = {"prompt": text, "model": model}
        resp = requests.post(
            f"{OLLAMA_URL}/api/embeddings",
            json=legacy_payload,
            timeout=120.0,
        )
        resp.raise_for_status()
        elapsed_ms = (time.perf_counter() - start) * 1000
        return resp.json()["embedding"], elapsed_ms

    resp.raise_for_status()
    elapsed_ms = (time.perf_counter() - start) * 1000
    return resp.json()["embeddings"][0], elapsed_ms


def embed_batch(texts: list[str], model: str, dimensions: int) -> tuple[list[list[float]], float]:
    """Embed multiple texts, return (vectors, total_time_ms)."""
    vectors = []
    total_ms = 0
    for text in texts:
        vec, ms = embed(text, model, dimensions)
        vectors.append(vec)
        total_ms += ms
    return vectors, total_ms


def check_model_available(model: str) -> bool:
    try:
        resp = requests.get(f"{OLLAMA_URL}/api/tags", timeout=10.0)
        names = [m["name"] for m in resp.json().get("models", [])]
        return any(model.split(":")[0] in n for n in names) or model in names
    except Exception:
        return False


def unload_model(model: str):
    try:
        requests.post(f"{OLLAMA_URL}/api/generate", json={"model": model, "keep_alive": 0}, timeout=30.0)
    except Exception:
        pass


def benchmark_model(model_name: str, dims: int, corpus: list[dict], test_pairs: list[dict]):
    """Benchmark a single model at given dimensions against real data."""
    print(f"\n  --- {model_name} @ {dims}d (corpus={len(corpus)}, queries={len(test_pairs)}) ---")

    # Embed all corpus abstracts
    corpus_texts = [doc["abstract"] for doc in corpus]
    corpus_dois = [doc["doi"] for doc in corpus]

    print(f"    Embedding {len(corpus_texts)} abstracts...", end=" ", flush=True)
    start = time.perf_counter()
    try:
        corpus_vecs, corpus_ms = embed_batch(corpus_texts, model_name, dims)
    except Exception as e:
        print(f"FAILED: {e}")
        return None
    corpus_time = time.perf_counter() - start
    avg_embed_ms = corpus_ms / len(corpus_texts)
    print(f"done in {corpus_time:.1f}s ({avg_embed_ms:.0f}ms avg)")

    # Test each query
    recall_at_1 = 0
    recall_at_5 = 0
    recall_at_10 = 0
    total = len(test_pairs)
    query_times = []

    for pair in test_pairs:
        try:
            query_vec, query_ms = embed(pair["query"], model_name, dims)
        except Exception as e:
            print(f"    ERROR embedding query: {e}")
            total -= 1
            continue
        query_times.append(query_ms)

        # Find target in corpus
        target_idx = None
        for i, doi in enumerate(corpus_dois):
            if doi == pair["target_doi"]:
                target_idx = i
                break

        if target_idx is None:
            total -= 1
            continue

        # Compute similarities and rank
        sims = [(i, cosine_similarity(query_vec, cv)) for i, cv in enumerate(corpus_vecs)]
        sims.sort(key=lambda x: x[1], reverse=True)
        ranked_idxs = [s[0] for s in sims]

        rank = ranked_idxs.index(target_idx) + 1
        if rank <= 1:
            recall_at_1 += 1
        if rank <= 5:
            recall_at_5 += 1
        if rank <= 10:
            recall_at_10 += 1

        status = f"rank={rank}" if rank <= 10 else f"rank={rank} MISS"
        if rank > 10:
            top_sim = sims[0][1]
            target_sim = next(s for i, s in sims if i == target_idx)
            print(f"    {status:<20} q=\"{pair['query'][:60]}...\" top1_sim={top_sim:.3f} target_sim={target_sim:.3f}")

    r1 = recall_at_1 / total if total else 0
    r5 = recall_at_5 / total if total else 0
    r10 = recall_at_10 / total if total else 0
    avg_query_ms = sum(query_times) / len(query_times) if query_times else 0

    print(f"    R@1={r1:.0%}  R@5={r5:.0%}  R@10={r10:.0%}  "
          f"AvgEmbedMs={avg_embed_ms:.0f}  AvgQueryMs={avg_query_ms:.0f}")

    return {
        "model": model_name,
        "dimensions": dims,
        "corpus_size": len(corpus),
        "num_queries": total,
        "recall_at_1": round(r1, 3),
        "recall_at_5": round(r5, 3),
        "recall_at_10": round(r10, 3),
        "avg_embed_ms": round(avg_embed_ms, 1),
        "avg_query_ms": round(avg_query_ms, 1),
        "total_embed_time_s": round(corpus_time, 1),
    }


def main():
    print("=" * 80)
    print("EMBEDDING MODEL BENCHMARK — REAL DATA FROM NEO4J")
    print("=" * 80)

    # Fetch real abstracts
    print(f"\nFetching {CORPUS_SIZE} real abstracts from Neo4j...")
    corpus = fetch_abstracts(CORPUS_SIZE)
    print(f"  Got {len(corpus)} abstracts (min length >100 chars)")

    if len(corpus) < 20:
        print("ERROR: Not enough abstracts for meaningful benchmark. Run make enrich-force first.")
        sys.exit(1)

    # Generate test queries from a subset of the corpus
    random.seed(42)  # Reproducible
    test_pairs = generate_queries_from_abstracts(corpus, NUM_TEST_PAIRS)
    print(f"  Generated {len(test_pairs)} query-abstract test pairs")

    # Show a few examples
    print("\n  Example test pairs:")
    for p in test_pairs[:3]:
        print(f"    Query: \"{p['query'][:80]}...\"")
        print(f"    Target: {p['target_doi']}")

    all_results = []

    for model_cfg in MODELS:
        model_name = model_cfg["name"]
        if not check_model_available(model_name):
            print(f"\n[SKIP] {model_name} — not pulled")
            continue

        print(f"\n{'=' * 80}")
        print(f"MODEL: {model_name}")

        # Unload other models
        for other in MODELS:
            if other["name"] != model_name:
                unload_model(other["name"])

        for dims in model_cfg["dimensions"]:
            result = benchmark_model(model_name, dims, corpus, test_pairs)
            if result:
                all_results.append(result)

        unload_model(model_name)
        time.sleep(2)

    # Summary
    print(f"\n\n{'=' * 80}")
    print(f"SUMMARY — {len(corpus)} real abstracts, {len(test_pairs)} queries")
    print(f"{'=' * 80}")
    print(f"{'Model':<30} {'Dims':>6} {'R@1':>6} {'R@5':>6} {'R@10':>6} {'EmbMs':>7} {'QryMs':>7} {'TotalS':>8}")
    print("-" * 85)

    for r in sorted(all_results, key=lambda x: (-x["recall_at_5"], -x["recall_at_1"], x["avg_embed_ms"])):
        print(f"{r['model']:<30} {r['dimensions']:>6} {r['recall_at_1']:>5.0%} {r['recall_at_5']:>5.0%} "
              f"{r['recall_at_10']:>5.0%} {r['avg_embed_ms']:>6.0f}ms {r['avg_query_ms']:>6.0f}ms {r['total_embed_time_s']:>7.1f}s")

    # Save results
    with open("/root/research-ai/scripts/benchmark_embed_results.json", "w") as f:
        json.dump(all_results, f, indent=2)
    print(f"\nRaw results saved to scripts/benchmark_embed_results.json")


if __name__ == "__main__":
    main()
