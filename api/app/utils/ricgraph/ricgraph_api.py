import os
from typing import Any, Dict, List, Literal, Optional
import requests

RICGRAPH_URL = os.getenv("RICGRAPH_URL")

def parse_response(data: Any) -> Any:
    """
    Unwrap the standard 'results' wrapper if present, otherwise return raw data.
    """
    if isinstance(data, dict):
        return data.get("results", data)
    return data

def make_ricgraph_request(
    method: Literal["GET", "POST"],
    endpoint: str,
    params: Optional[Dict[str, Any]] = None,
    body: Optional[Dict[str, Any]] = None,
    session: Optional[requests.Session] = None,
) -> Any:
    """
    Make a GET or POST request to the Ricgraph API.

    Args:
        method:   HTTP method, either "GET" or "POST".
        endpoint: The API endpoint path (e.g. "/autocomplete").
        params:   Optional query parameters to append to the URL.
        body:     Optional JSON body (used for POST requests).
        session:  Optional requests.Session to reuse connections.

    Returns:
        Any: The JSON response body, unwrapped from a 'results' key when present.
             Returns an empty list on failure.
    """
    url = f"{RICGRAPH_URL}{endpoint}"

    clean_params = {k: v for k, v in (params or {}).items() if v is not None}
    clean_body = {k: v for k, v in (body or {}).items() if v is not None}

    http = session or requests.Session()
    try:
        response = http.request(
            method,
            url,
            params=clean_params or None,
            json=clean_body or None,
            timeout=30,
        )
        response.raise_for_status()
        return parse_response(response.json())
    except requests.RequestException as e:
        print(f"{method} request to {endpoint} failed: {e}")
        return []

def make_autocomplete_request(query: str, limit: int = 10) -> List[Dict[str, Any]]:
    """
    [POST /autocomplete] Search for autocomplete suggestions.

    Args:
        query: The partial text to autocomplete.
        limit: Maximum number of suggestions to return (1-100, default 10).

    Returns:
        A list of dicts with keys: id, displayName, type, bestScore.
    """
    return make_ricgraph_request("POST", "/autocomplete", body={"query": query, "limit": limit})
