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

import logging

from fastapi import APIRouter, Query, HTTPException
from neo4j.exceptions import ServiceUnavailable

from app.utils.ricgraph_utils.autocomplete_utils import (
    get_autocomplete_suggestions,
    AutocompleteError,
    InvalidQueryError,
)
from app.utils.schemas import Suggestions

log = logging.getLogger(__name__)

router = APIRouter(prefix="/autocomplete")

@router.get("", response_model=Suggestions)
def suggest(
    query: str,
    limit: int = Query(
        10,
        ge=1,
        le=100,
        description="Maximum number of suggestions to return (1-100)",
    ),
):
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
    except ServiceUnavailable:
        # Neo4j is temporarily unavailable – signal this as a 503 to clients.
        log.warning("Autocomplete service unavailable for query=%r", query)
        raise HTTPException(status_code=503, detail="Autocomplete service unavailable.")
    except AutocompleteError:
        log.error("Autocomplete service error for query=%r", query)
        raise HTTPException(status_code=500, detail="Autocomplete query failed.")
    except RuntimeError:
        # Typically raised when the Neo4j driver has not been initialized yet.
        log.error("Autocomplete backend not initialized for query=%r", query)
        raise HTTPException(status_code=503, detail="Autocomplete backend not initialized.")
    except Exception:
        log.error("Unexpected error while handling autocomplete for query=%r", query)
        raise HTTPException(status_code=500, detail="Autocomplete query failed.")
        