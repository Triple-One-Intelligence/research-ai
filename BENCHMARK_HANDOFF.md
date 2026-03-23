# AI Model Benchmark Handoff — A10 GPU Server

You are working on the `research-ai` project. This server has an **NVIDIA A10 GPU (24GB VRAM)**. Your task is to benchmark candidate AI models (both chat/LLM and embedding) to find the best setup for our use case, then update the configuration.

## Context

We run **Ollama** (`docker.io/ollama/ollama:latest`) in a Podman container with full GPU passthrough. The Ollama API is at `http://127.0.0.1:11434` on the host (internal: `http://research-ai-ai:11434`).

### What this system does
- **RAG over scientific publications**: We have Dutch and English scientific paper abstracts stored in Neo4j with vector embeddings.
- **Embedding pipeline**: `make enrich` fetches abstracts from OpenAlex, embeds them via Ollama, stores embedding + abstract on Neo4j nodes.
- **Query flow**: User prompt → embed prompt via Ollama → vector similarity search in Neo4j (`db.index.vector.queryNodes`) → retrieve top-K publications → build RAG context → stream LLM response via Ollama `/api/chat`.
- **HyDE**: We compute Hypothetical Document Embeddings at query time, so the real-time embedding call is just one short text.

### Current models
- **Chat**: `tinyllama` (prod default — this is bad, it was a placeholder)
- **Embeddings**: `nomic-embed-text` at 768 dimensions (prod), `snowflake-arctic-embed2` at 1024 dimensions (dev)

### Key files
- `api/app/utils/ai_utils/ai_utils.py` — Single source of truth for `AI_SERVICE_URL`, `CHAT_MODEL`, `EMBED_MODEL`, `EMBED_DIMENSIONS`
- `api/app/routers/ai.py` — RAG endpoint (`/generate`), chat endpoint (`/chat`), streaming SSE proxy to Ollama
- `api/app/scripts/enrich.py` — Batch enrichment: fetches abstracts, generates embeddings, stores in Neo4j
- `api/app/utils/database_utils/database_utils.py` — `ensure_vector_index()` creates/recreates the Neo4j vector index (auto-handles dimension changes)
- `kube/research-ai-prod.env.example` — Production env template (EMBED_MODEL, EMBED_DIMENSIONS, CHAT_MODEL)
- `Makefile` — `make deploy` pulls models, `make enrich` / `make enrich-force` runs enrichment

### How model config works
Everything is env-var driven. To change models you only need to update the `.env` file:
```
CHAT_MODEL=qwen3:30b-a3b
EMBED_MODEL=qwen3-embedding:8b
EMBED_DIMENSIONS=4096
```
Then restart the API container and re-run `make enrich-force` if the embedding model changed.

The vector index in Neo4j auto-detects dimension mismatches and recreates itself (see `ensure_vector_index()` in `database_utils.py`).

---

## Task 1: Benchmark Chat/LLM Models

### Candidate models to test (all fit on A10 24GB at Q4_K_M)

| Model | Ollama name | VRAM est. | Why test it |
|---|---|---|---|
| Qwen3 30B-A3B (MoE) | `qwen3:30b-a3b` | ~18.6 GB | MoE = 30B knowledge, 3B active. Should be fast AND smart. Top pick. |
| Gemma 3 27B QAT | `gemma3:27b` | ~14.1 GB | Google's quantization-aware trained model. Small footprint for 27B. |
| Command-R 35B | `command-r:35b` | ~21.5 GB | Purpose-built for RAG with grounded citations. Tight fit. |
| Qwen 2.5 14B | `qwen2.5:14b` | ~10.7 GB | Safe middle ground, fast, good multilingual. |
| Gemma 3 12B | `gemma3:12b` | ~8.1 GB | Fastest option, baseline comparison. |

### How to benchmark

1. **Pull all candidate models:**
```bash
for model in qwen3:30b-a3b gemma3:27b command-r:35b qwen2.5:14b gemma3:12b; do
  curl -s http://127.0.0.1:11434/api/pull -d "{\"name\":\"$model\"}" | tail -1
  echo ""
done
```

2. **Create a benchmark script** (`scripts/benchmark_chat.sh` or Python) that:
   - Defines 3-5 realistic RAG prompts in both Dutch and English, e.g.:
     - "What research has been done on machine learning applications in healthcare at Utrecht University?"
     - "Welke publicaties gaan over duurzame energie en klimaatverandering?"
     - "Summarize the key findings on antibiotic resistance from recent publications"
     - A longer, more complex multi-part question
   - For each model, for each prompt:
     - Sends a POST to `http://127.0.0.1:11434/api/chat` with a realistic system prompt (copy the format from `_build_rag_system_prompt` in `ai.py` — include some fake publication context)
     - Measures: **time to first token**, **total generation time**, **tokens per second** (Ollama returns this in the final chunk's `eval_count` / `eval_duration` fields)
     - Evaluates response quality subjectively: does it stay grounded? Does it handle Dutch? Is it coherent?
   - Runs each prompt 3 times per model (first run will be cold-load, subsequent are warm)
   - **Important**: Only one model can be loaded in VRAM at a time on A10. Between models, unload the previous one:
     ```bash
     curl -s http://127.0.0.1:11434/api/generate -d '{"model":"MODEL_NAME","keep_alive":0}'
     ```

3. **Quick alternative** — use `--verbose` flag:
```bash
ollama run qwen3:30b-a3b --verbose
```
Then paste a prompt. It prints `eval rate: XX.XX tokens/s` after each response.

### What to measure and compare
- **Tokens/sec** (eval rate) — must produce a full answer in under 20 seconds
- **Quality**: Does it follow RAG grounding instructions? Does it cite the provided publications?
- **Dutch handling**: Can it respond in Dutch when prompted in Dutch?
- **Hallucination**: Does it make up facts not in the provided context?

---

## Task 2: Benchmark Embedding Models

### Candidate models

| Model | Ollama name | Dimensions | Why test it |
|---|---|---|---|
| Qwen3 Embedding 8B | `qwen3-embedding:8b` | up to 4096 | #1 on MTEB multilingual leaderboard. Best quality. |
| Qwen3 Embedding 4B | `qwen3-embedding:4b` | up to 2560 | Lighter alternative, still excellent. |
| BGE-M3 | `bge-m3` | 1024 | Proven multilingual, dense+sparse, small (1.2GB). |
| snowflake-arctic-embed2 | `snowflake-arctic-embed2` | 1024 | Current dev model — baseline comparison. |
| nomic-embed-text | `nomic-embed-text` | 768 | Current prod model — baseline. |

### How to benchmark embeddings

Embedding quality is harder to benchmark locally than chat. Here's the approach:

1. **Pull all candidate models:**
```bash
for model in qwen3-embedding:8b qwen3-embedding:4b bge-m3 snowflake-arctic-embed2 nomic-embed-text; do
  curl -s http://127.0.0.1:11434/api/pull -d "{\"name\":\"$model\"}" | tail -1
  echo ""
done
```

2. **Create a benchmark script** (`scripts/benchmark_embed.sh` or Python) that:
   - Prepares ~10 test pairs: (query, relevant_abstract) where you know the query SHOULD match the abstract. Include:
     - Dutch queries matching Dutch abstracts
     - English queries matching English abstracts
     - Cross-language: Dutch query that should match English abstract (and vice versa)
     - Scientific jargon queries
     - A few negative pairs (query that should NOT match an abstract)
   - For each embedding model:
     - Embed all queries and all abstracts
     - Compute cosine similarity between each query and each abstract
     - Check: do the correct pairs have the highest similarity? (This is basically recall@1 / recall@5)
     - Measure embedding speed (ms per text)
   - Compare models on: **retrieval accuracy** (correct matches), **cross-lingual quality**, **speed**

3. **Dimension testing for Qwen3-Embedding**: This model supports flexible dimensions (32-4096). Test at 1024, 2048, and 4096 to see if higher dims actually improve retrieval for your data, or if the gains plateau.

### Re-indexing after choosing

Once you pick the best embedding model:
1. Update `.env`: `EMBED_MODEL=chosen_model`, `EMBED_DIMENSIONS=chosen_dims`
2. Restart the API container
3. Run `make enrich-force` — this will:
   - Call `ensure_vector_index()` which detects the dimension mismatch, drops and recreates the index
   - Re-embed ALL abstracts with the new model
   - Store new embeddings in Neo4j

---

## Neo4j and Higher Dimensions — What to Expect

Neo4j uses **HNSW (Hierarchical Navigable Small World)** for vector search. Impact of higher dimensions:

- **Query speed**: Minimal impact. HNSW limits the number of distance computations regardless of dimensionality. Each individual cosine similarity computation is O(d) where d = dimensions, so 4096d is ~4x more work per comparison than 1024d, but HNSW typically only computes ~100-300 similarities per query. You're looking at maybe **1-5ms extra per query** — negligible compared to LLM inference time.
- **RAM usage**: Linear with dimensions. Each float32 vector: `dims × 4 bytes`. For 10,000 abstracts: 1024d = ~40MB, 4096d = ~160MB. Plus HNSW graph overhead (~1.5-2x). Still very manageable.
- **Storage**: Same linear scaling. Not a concern for academic paper counts.
- **Index build time**: Slightly slower with higher dims, but this is a one-time cost during `make enrich-force`.

**Bottom line**: Higher dimensions are effectively free for your dataset size. Go with whatever gives the best retrieval quality.

---

## Task 3: Apply the Winners

After benchmarking, update these files:

1. **`.env` file on the server** (the actual one, not the example):
```
CHAT_MODEL=<winning chat model>
EMBED_MODEL=<winning embed model>
EMBED_DIMENSIONS=<chosen dimensions>
```

2. **`kube/research-ai-prod.env.example`** — update the defaults to match so future deploys use the right models.

3. **`Makefile`** — the model-pull loop in `make deploy` hardcodes `nomic-embed-text` and `tinyllama` as fallbacks. Update these to the new defaults.

4. **Restart and re-enrich:**
```bash
# Restart API to pick up new env vars
sudo systemctl restart research-ai-api.service

# Re-embed everything with new model (this takes a while)
make enrich-force
```

5. **Verify**: Run a few test queries through `/generate` and check that results are sensible.

---

## Notes

- The Ollama container is at `research-ai-ai.service` (Podman Quadlet). Config: `kube/research-ai-ai.container`.
- GPU config is already set: `NVIDIA_VISIBLE_DEVICES=all`, `NVIDIA_DRIVER_CAPABILITIES=compute,utility`.
- Models persist in the `ai-data` Podman volume at `/root/.ollama`.
- You can import any HuggingFace GGUF model not in Ollama's library: `ollama run hf.co/username/repo:quantization`.
- If a model is too large for 24GB VRAM, Ollama will partially offload to CPU — this will be obvious from terrible tokens/sec. If you see <5 tok/s, the model doesn't fit.
