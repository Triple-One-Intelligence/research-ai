from fastapi import APIRouter
from pydantic import BaseModel
from typing import List
from app.schemas import Person, Publication, Organization, Connections


router = APIRouter(prefix = "/autocomplete")

class Suggestions(BaseModel):
    persons: List[Person]
    Organizations: List[Organization]


@router.get("/", response_model=Suggestions)
def suggest(query: str, types: List[str], limit: int):
    return Suggestions(
        persons=[Person(author_id="1", name="testpersoon")],
        organizations=[Organization(organization_id="2", name="testorg")]
    )