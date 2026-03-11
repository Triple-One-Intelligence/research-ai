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

from fastapi import APIRouter, Query, HTTPException
from app.utils.ricgraph_utils.autocomplete_utils import get_autocomplete_suggestions, AutocompleteError, InvalidQueryError
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
    try:
        suggestions = get_autocomplete_suggestions(query, limit)
        return suggestions
    except InvalidQueryError as exception:
        raise HTTPException(status_code=400, detail=str(exception))
    except AutocompleteError:
        print(f"Autocomplete service error for query={query!r}")
        raise HTTPException(status_code=500, detail="Autocomplete query failed.")
    except Exception:
        print(f"Unexpected error while handling autocomplete for query={query!r}")
        raise HTTPException(status_code=500, detail="Autocomplete query failed.")