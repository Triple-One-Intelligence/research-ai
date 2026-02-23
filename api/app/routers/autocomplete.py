from app.utils.ricgraph.autocomplete_utils import autocomplete
from app.utils.schemas import Suggestions
from fastapi import APIRouter

router = APIRouter(prefix="/autocomplete")


@router.get("", response_model=Suggestions)
def suggest(query: str, limit: int = 10):
    results = autocomplete(query, limit)
    return results
