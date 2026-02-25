"""
API router for autocomplete suggestions.

This module exposes a FastAPI router that provides an endpoint for
retrieving autocomplete suggestions from the internal ricgraph utility.

Endpoint
- GET /autocomplete
  - query: str (required)  -- the partial text to autocomplete
  - limit: int (optional)  -- maximum number of suggestions to return (default: 10, validated 1-100)
  - response: Suggestions  -- pydantic model defined in `app.utils.schemas`
"""

from fastapi import APIRouter, Query
from app.utils.ricgraph.autocomplete_utils import autocomplete
# Import the pydantic response model used by FastAPI to serialize responses
from app.utils.schemas import Suggestions

router = APIRouter(prefix="/autocomplete")


@router.get("", response_model=Suggestions)
def suggest(query: str, limit: int = Query(10, ge=1, le=100, description="Maximum number of suggestions to return (1-100)")):
    """
    Endpoint GET /autocomplete

    Suggest autocomplete completions for a partial query.

    Parameters
    - query: str (required)  -- the partial text to autocomplete
    - limit: int (optional)  -- maximum number of suggestions to return (default: 10)

    Returns
    - An instance of the `Suggestions` pydantic model. FastAPI will convert the
      returned object into JSON according to the model schema.
    """
    # Delegate the actual autocomplete functionality to the utility function and return its result.
    return autocomplete(query, limit)