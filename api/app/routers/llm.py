from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter(prefix="/llm", tags=["llm"])

# wat frontend stuurt
class LLMRequest(BaseModel):
    prompt: str

# wat backend terugstuurt
class LLMResponse(BaseModel):
    answer: str

@router.post("/answer", response_model=LLMResponse)
def get_llm_answer(req: LLMRequest):

    # voor nu mock antwoord
    return LLMResponse(answer=f"mock antwoord op prompt: {req.prompt}")
