from app.utils.ricgraph.autocomplete_utils import autocomplete
from fastapi import APIRouter
from pydantic import BaseModel
from typing import List
from app.schemas import Person, Publication, Organization, Connections


router = APIRouter(prefix = "/autocomplete")

class Suggestions(BaseModel):
    persons: List[Person]
    organizations: List[Organization]


@router.get("", response_model=Suggestions)
def suggest(query: str, limit: int = 10):
    results = autocomplete(query, limit)
    return results