import json
import logging
from typing import TypedDict

import httpx
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from app.utils.database_utils.database_utils import get_graph, VECTOR_INDEX_NAME
# Refactoring: Shotgun Surgery fix — constants centralized in ai_utils
from app.utils.ai_utils.ai_utils import (
    AI_SERVICE_URL, CHAT_MODEL, async_embed, send_async_ai_request,
)
from app.utils.ricgraph_utils.queries import rag_queries
from app.utils.schemas.ai import (
    ChatRequest, EmbedRequest, EntityRef, RagGenerateRequest,
)

router = APIRouter()
log = logging.getLogger(__name__)

@router.post("/prompt1")
async def chat(req: ChatRequest):
    """Streaming chat without RAG context."""
    payload = req.model_dump(exclude_none=True)
    payload["model"] = CHAT_MODEL  # Always use the configured model
    payload["stream"] = True
    return _streaming_chat_response(payload)



@router.get("/prompt_top5publications", response_model=Suggestions)
def _stream_prompt1_response(
    selected_entity: EntityRef,
    language: str = "English"
):
    return _stream_prompt1_response()