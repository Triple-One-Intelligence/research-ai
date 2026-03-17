#!/usr/bin/env python3
"""Benchmark chat/LLM models on Ollama for RAG use case — REAL DATA version.

Pulls actual abstracts from Neo4j and tests with realistic context sizes
(15-20 publications in context, ~2000-3000 input tokens).
Tests: tokens/sec, time to first token, total time, response quality.
"""

import json
import os
import random
import time
import sys
import requests

OLLAMA_URL = "http://127.0.0.1:11434"
NEO4J_URL = "http://localhost:7474"

MODELS = [
    "qwen3:30b-a3b",
    "gemma3:27b",
    "command-r:35b",
    "qwen2.5:14b",
    "gemma3:12b",
]

# How many publications to include in RAG context per prompt
CONTEXT_SIZE = 15

RUNS_PER_PROMPT = 3

SYSTEM_PROMPT_TEMPLATE = """Use ONLY the given context data as evidence. Be concise, neutral, and avoid speculation beyond the evidence. If evidence is insufficient, say so briefly.

{entity_context}
Relevant publications:
{publications}"""


def neo4j_query(statement: str, params: dict = None):
    """Run a Cypher query via Neo4j HTTP API."""
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


def fetch_publications_for_context(n: int) -> list[dict]:
    """Fetch real publications with abstracts from Neo4j."""
    rows = neo4j_query(
        "MATCH (n:RicgraphNode) WHERE n.name = 'DOI' AND n.abstract IS NOT NULL "
        "AND n.abstract <> '' AND size(n.abstract) > 100 "
        "RETURN n.value AS doi, n.abstract AS abstract, n.comment AS title, "
        "n.category AS category "
        "ORDER BY rand() LIMIT $limit",
        {"limit": n},
    )
    return [{"doi": r["row"][0], "abstract": r["row"][1], "title": r["row"][2], "category": r["row"][3]} for r in rows]


def format_publications(pubs: list[dict]) -> str:
    """Format publications for RAG context (mirrors format_similar_publications_for_rag)."""
    lines = []
    for doc in pubs:
        parts = [
            f"DOI: {doc.get('doi', 'n/a')}",
            f"Title: {doc.get('title', 'n/a')}",
        ]
        if doc.get("category"):
            parts.append(f"Category: {doc['category']}")
        if doc.get("abstract"):
            parts.append(f"Abstract: {doc['abstract']}")
        lines.append(" | ".join(parts))
    return "\n\n".join(lines)


def build_prompts(all_pubs: list[dict]) -> list[dict]:
    """Build realistic test prompts using real publication data."""
    prompts = []

    # Select different subsets for each prompt's context
    random.seed(42)

    # Prompt 1: English broad topic query
    ctx1 = random.sample(all_pubs, min(CONTEXT_SIZE, len(all_pubs)))
    prompts.append({
        "name": "EN: Broad topic",
        "text": "What are the main research themes and findings across these publications?",
        "context": ctx1,
        "entity_context": "",
    })

    # Prompt 2: Dutch query
    ctx2 = random.sample(all_pubs, min(CONTEXT_SIZE, len(all_pubs)))
    prompts.append({
        "name": "NL: Dutch query",
        "text": "Welke publicaties gaan over data management of softwareontwikkeling? Geef een samenvatting in het Nederlands.",
        "context": ctx2,
        "entity_context": "",
    })

    # Prompt 3: Specific person entity context
    ctx3 = random.sample(all_pubs, min(CONTEXT_SIZE, len(all_pubs)))
    prompts.append({
        "name": "EN: Person-scoped",
        "text": "What are this researcher's main contributions and research focus areas?",
        "context": ctx3,
        "entity_context": "The following user query is related to a person named 'Dr. Example Researcher'.\n",
    })

    # Prompt 4: Grounding test — ask about something NOT in context
    ctx4 = random.sample(all_pubs, min(CONTEXT_SIZE, len(all_pubs)))
    prompts.append({
        "name": "EN: Grounding (no evidence)",
        "text": "What does the research say about cryptocurrency regulation in the European Union?",
        "context": ctx4,
        "entity_context": "",
    })

    # Prompt 5: Complex multi-part Dutch
    ctx5 = random.sample(all_pubs, min(CONTEXT_SIZE, len(all_pubs)))
    prompts.append({
        "name": "NL: Complex multi-part",
        "text": "Analyseer de methodologische aanpak van deze publicaties. Welke onderzoeksmethoden worden het meest gebruikt en wat zijn de gemeenschappelijke beperkingen?",
        "context": ctx5,
        "entity_context": "",
    })

    return prompts


def unload_model(model: str):
    """Unload a model from VRAM."""
    try:
        requests.post(
            f"{OLLAMA_URL}/api/generate",
            json={"model": model, "keep_alive": 0},
            timeout=30.0,
        )
    except Exception:
        pass


def check_model_available(model: str) -> bool:
    """Check if a model is pulled."""
    try:
        resp = requests.get(f"{OLLAMA_URL}/api/tags", timeout=10.0)
        tags = resp.json()
        names = [m["name"] for m in tags.get("models", [])]
        return model in names or f"{model}:latest" in names or any(model in n for n in names)
    except Exception:
        return False


def benchmark_single(model: str, prompt: dict, run_num: int) -> dict:
    """Run a single benchmark: send chat request, measure timing."""
    pub_context = format_publications(prompt["context"])
    system_prompt = SYSTEM_PROMPT_TEMPLATE.format(
        publications=pub_context,
        entity_context=prompt.get("entity_context", ""),
    )

    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt["text"]},
        ],
        "stream": True,
    }

    # Estimate input tokens (~4 chars per token)
    input_chars = len(system_prompt) + len(prompt["text"])
    est_input_tokens = input_chars // 4

    first_token_time = None
    start = time.perf_counter()
    full_response = ""
    eval_count = 0
    eval_duration = 0
    prompt_eval_count = 0
    prompt_eval_duration = 0

    try:
        resp = requests.post(
            f"{OLLAMA_URL}/api/chat",
            json=payload,
            stream=True,
            timeout=180.0,
        )
        resp.raise_for_status()
        for line in resp.iter_lines():
            if not line:
                continue
            chunk = json.loads(line)
            token = chunk.get("message", {}).get("content", "")
            if token and first_token_time is None:
                first_token_time = time.perf_counter()
            if token:
                full_response += token
            if chunk.get("done"):
                eval_count = chunk.get("eval_count", 0)
                eval_duration = chunk.get("eval_duration", 0)
                prompt_eval_count = chunk.get("prompt_eval_count", 0)
                prompt_eval_duration = chunk.get("prompt_eval_duration", 0)
    except Exception as e:
        return {"error": str(e)}

    end = time.perf_counter()
    total_time = end - start
    ttft = (first_token_time - start) if first_token_time else total_time

    # Ollama reports durations in nanoseconds
    tps = (eval_count / (eval_duration / 1e9)) if eval_duration > 0 else 0
    prompt_tps = (prompt_eval_count / (prompt_eval_duration / 1e9)) if prompt_eval_duration > 0 else 0

    return {
        "model": model,
        "prompt": prompt["name"],
        "run": run_num,
        "ttft_s": round(ttft, 2),
        "total_s": round(total_time, 2),
        "eval_tokens": eval_count,
        "tokens_per_sec": round(tps, 1),
        "prompt_tokens": prompt_eval_count,
        "prompt_tps": round(prompt_tps, 1),
        "est_input_tokens": est_input_tokens,
        "context_pubs": len(prompt["context"]),
        "response_preview": full_response[:300],
        "response_length": len(full_response),
    }


def main():
    print("=" * 80)
    print("CHAT MODEL BENCHMARK — REAL DATA FROM NEO4J")
    print("=" * 80)

    # Fetch real publications
    print(f"\nFetching publications from Neo4j for RAG context (up to {CONTEXT_SIZE * 5} unique)...")
    all_pubs = fetch_publications_for_context(CONTEXT_SIZE * 5)
    print(f"  Got {len(all_pubs)} publications with abstracts")

    if len(all_pubs) < CONTEXT_SIZE:
        print(f"ERROR: Need at least {CONTEXT_SIZE} publications. Run make enrich-force first.")
        sys.exit(1)

    # Build prompts with real context
    prompts = build_prompts(all_pubs)

    # Show context size info
    sample_ctx = format_publications(prompts[0]["context"])
    est_tokens = len(sample_ctx) // 4
    print(f"  Context size per prompt: ~{est_tokens} tokens ({len(prompts[0]['context'])} pubs, {len(sample_ctx)} chars)")

    # Filter to available models
    available = []
    for m in MODELS:
        if check_model_available(m):
            available.append(m)
            print(f"  [OK] {m}")
        else:
            print(f"  [SKIP] {m} — not pulled")

    if not available:
        print("No models available! Pull them first.")
        sys.exit(1)

    all_results = []

    for model in available:
        print(f"\n{'=' * 80}")
        print(f"MODEL: {model}")
        print(f"{'=' * 80}")

        # Unload any previous model
        for prev in available:
            if prev != model:
                unload_model(prev)

        for prompt in prompts:
            for run in range(1, RUNS_PER_PROMPT + 1):
                label = f"  [{prompt['name']}] run {run}/{RUNS_PER_PROMPT}"
                print(f"{label}...", end=" ", flush=True)

                result = benchmark_single(model, prompt, run)
                all_results.append(result)

                if "error" in result:
                    print(f"ERROR: {result['error']}")
                    result["model"] = model
                    result["prompt"] = prompt["name"]
                    result["run"] = run
                else:
                    print(
                        f"TTFT={result['ttft_s']}s  "
                        f"Total={result['total_s']}s  "
                        f"Tok/s={result['tokens_per_sec']}  "
                        f"OutTok={result['eval_tokens']}  "
                        f"InTok={result['prompt_tokens']}  "
                        f"PromptTPS={result['prompt_tps']}"
                    )

        # Print response samples for quality review
        print(f"\n--- Response samples for {model} ---")
        seen_prompts = set()
        for r in all_results:
            if r["model"] == model and r.get("run") == 1 and r["prompt"] not in seen_prompts:
                seen_prompts.add(r["prompt"])
                print(f"\n  [{r['prompt']}]")
                print(f"  {r.get('response_preview', 'N/A')}")

        # Unload model
        unload_model(model)
        time.sleep(2)

    # Summary table
    print(f"\n\n{'=' * 80}")
    print(f"SUMMARY (warm runs avg, runs 2-3) — {CONTEXT_SIZE} pubs in context")
    print(f"{'=' * 80}")
    print(f"{'Model':<25} {'Tok/s':>8} {'TTFT':>8} {'Total':>8} {'OutTok':>8} {'InTok':>8} {'PrTPS':>8}")
    print("-" * 85)

    for model in available:
        warm = [r for r in all_results if r["model"] == model and r.get("run", 1) > 1 and "error" not in r]
        if not warm:
            warm = [r for r in all_results if r["model"] == model and "error" not in r]
        if warm:
            avg_tps = sum(r["tokens_per_sec"] for r in warm) / len(warm)
            avg_ttft = sum(r["ttft_s"] for r in warm) / len(warm)
            avg_total = sum(r["total_s"] for r in warm) / len(warm)
            avg_out = sum(r["eval_tokens"] for r in warm) / len(warm)
            avg_in = sum(r["prompt_tokens"] for r in warm) / len(warm)
            avg_ptps = sum(r["prompt_tps"] for r in warm) / len(warm)
            print(f"{model:<25} {avg_tps:>8.1f} {avg_ttft:>7.2f}s {avg_total:>7.2f}s {avg_out:>8.0f} {avg_in:>8.0f} {avg_ptps:>8.1f}")

    # Save raw results
    with open("/root/research-ai/scripts/benchmark_chat_results.json", "w") as f:
        json.dump(all_results, f, indent=2)
    print(f"\nRaw results saved to scripts/benchmark_chat_results.json")


if __name__ == "__main__":
    main()
