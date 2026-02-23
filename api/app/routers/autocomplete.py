from app.utils.ricgraph.autocomplete_utils import autocomplete
from fastapi import APIRouter
from pydantic import BaseModel
from typing import List
from app.utils.schemas import Person, Publication, Organization, Connections, Suggestions


router = APIRouter(prefix = "/autocomplete")

@router.get("", response_model=Suggestions)
def suggest(query: str, limit: int = 10):
    results = autocomplete(query, limit)
    return results