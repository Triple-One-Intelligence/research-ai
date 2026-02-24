from typing import Any, Dict, List, Optional

import requests

# Allow overriding the Ricgraph base URL via environment variable.
BASE_URL = "http://localhost:3030/api"


def make_ricgraph_request(
    endpoint: str, body: Dict[str, Any], session: Optional[requests.Session] = None
) -> Any:
    """
    Generic function to make a POST request to the Ricgraph API.

    Returns:
        Any: The JSON response body. Types are relaxed (Any) to accommodate
        endpoints that return lists, dicts, or other structures.
    """
    url = f"{BASE_URL}{endpoint}"

    # Remove None values to avoid sending empty keys
    clean_body = {k: v for k, v in body.items() if v is not None}

    http = session or requests.Session()
    try:
        response = http.post(url, json=clean_body, timeout=30)
        response.raise_for_status()

        data = response.json()

        # If the API returns a standard 'results' wrapper, unwrap it.
        # Otherwise return the raw data (which might be a dict or a list).
        if isinstance(data, dict):
            return data.get("results", data)
        return data

    except requests.RequestException as e:
        print(f"Request to {endpoint} failed: {e}")
        return []

def execute_query(query: str, **params) -> List[Dict[str, Any]]:
    """[POST /query] Execute a custom query against the Ricgraph database."""
    return make_ricgraph_request("/query", {"query": query, "params": params})
