import gc
from typing import List, Optional
from fastapi import APIRouter
from pydantic import BaseModel

try:
    from llama_cpp import Llama
    AI_AVAILABLE = True
except:
    AI_AVAILABLE = False
    Llama = None

router = APIRouter(prefix="/ai", tags=["AI Models"])

CURRENT_LLM = None
CURRENT_MODEL_ID = ""

def load_model(repo_id, filename, embedding):
    global CURRENT_LLM, CURRENT_MODEL_ID
    
    if not AI_AVAILABLE:
        return None

    new_id = f"{repo_id}-{filename}-{embedding}"
    
    if CURRENT_LLM and CURRENT_MODEL_ID == new_id:
        return CURRENT_LLM

    if CURRENT_LLM:
        del CURRENT_LLM
        gc.collect()

    CURRENT_LLM = Llama.from_pretrained(
        repo_id=repo_id,
        filename=filename,
        n_gpu_layers=-1,
        embedding=embedding,
        verbose=True
    )
    CURRENT_MODEL_ID = new_id
    return CURRENT_LLM

class ChatRequest(BaseModel):
    repo_id: str
    filename: str
    prompt: str
    
    class Config:
        json_schema_extra = {
            "example": {
                "repo_id": "Qwen/Qwen2.5-0.5B-Instruct-GGUF",
                "filename": "*q8_0.gguf",
                "prompt": "Explain 3 benefits of running AI locally."
            }
        }

class EmbedRequest(BaseModel):
    repo_id: str
    filename: str
    texts: List[str]

@router.post("/chat")
def chat(req: ChatRequest):
    if not AI_AVAILABLE:
        return {"text": "MOCK RESPONSE: No GPU found, but the API works!"}

    llm = load_model(req.repo_id, req.filename, embedding=False)
    output = llm.create_completion(prompt=req.prompt, max_tokens=256)
    return {"text": output["choices"][0]["text"]}

@router.post("/embed")
def embed(req: EmbedRequest):
    if not AI_AVAILABLE:
        return {"embeddings": [[0.1, 0.2, 0.3] for _ in req.texts]}

    llm = load_model(req.repo_id, req.filename, embedding=True)
    results = []
    for text in req.texts:
        res = llm.create_embedding(text)
        results.append(res["data"][0]["embedding"])
    return {"embeddings": results}