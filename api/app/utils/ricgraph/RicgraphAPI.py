import os
import requests
from typing import List, Dict, Any, Optional

# Allow overriding the Ricgraph base URL via environment variable.
BASE_URL = "http://localhost:3030/api"

def make_ricgraph_request(
    endpoint: str,
    params: Dict[str, Any],
    session: Optional[requests.Session] = None
) -> Any:
    """
    Generic function to make a GET request to the Ricgraph API.
    
    Returns:
        Any: The JSON response body. Types are relaxed (Any) to accommodate 
        endpoints that return lists, dicts, or other structures.
    """
    url = f"{BASE_URL}{endpoint}"
    # Remove None values from params to avoid sending empty keys
    clean_params = {k: v for k, v in params.items() if v is not None}
    
    http = session or requests.Session()
    try:
        response = http.get(url, params=clean_params, timeout=30)
        response.raise_for_status()
        
        data = response.json()
        
        # If the API returns a standard 'results' wrapper, unwrap it.
        # Otherwise return the raw data (which might be a dict or a list).
        if isinstance(data, dict):
            return data.get("results", data)
        return data

    except requests.RequestException as e:
        print(f"[Ricgraph Error] Request to {endpoint} failed: {e}")
        return []

def search_person(value: str, max_nr_items: int = 10) -> List[Dict[str, Any]]:
    """[GET /person/search] Search for a person."""
    return make_ricgraph_request("/person/search", {"value": value, "max_nr_items": max_nr_items})

def search_organization(value: str, max_nr_items: int = 10) -> List[Dict[str, Any]]:
    """[GET /organization/search] Search for an organization."""
    return make_ricgraph_request("/organization/search", {"value": value, "max_nr_items": max_nr_items})