from typing import List, Dict, Union
from app.utils.ricgraph.RicgraphAPI import (
    search_person, 
    search_organization
)
from app.schemas import Person, Organization

def autocomplete(query: str, limit: int = 10) -> Dict[str, List[Union[Person, Organization]]]:
    """
    Search for persons and organizations, remove duplicates, 
    and rank results by relevance and label quality.
    """
    query = (query or "").strip()
    if len(query) < 2:
        return {"persons": [], "organizations": []}

    try:
        # Fetch enough raw data so we can deduplicate and still have enough results
        search_pool = limit * 2
        raw_persons = search_person(value=query, max_nr_items=search_pool)
        raw_orgs = search_organization(value=query, max_nr_items=search_pool)
    except Exception as e:
        print(f"Error: {e}")
        return {"persons": [], "organizations": []}

    # Use one dictionary to track all unique entities across the whole search
    # key: node_id, value: {score, label, category, data_object}
    results = {}

    def process_nodes(nodes, category):
        for node in nodes:
            node_id = node.get("_key")
            if not node_id: continue
            
            display_label = strip_uuid_hash(node.get("value", ""))
            
            # Calculate Relevance Score
            score = 1.0
            if display_label.lower().startswith(query.lower()):
                score += 1.0 
            
            if node_id not in results:
                # Create entry
                if category == "person":
                    data = Person(author_id=node_id, name=display_label)
                else:
                    data = Organization(organization_id=node_id, name=display_label)
                
                results[node_id] = {"score": score, "label": display_label, "category": category, "data": data}
            else:
                # Node already exists, pick the best label
                existing = results[node_id]
                best_label = determine_best_label(existing["label"], display_label)
                existing["label"] = best_label
                existing["data"].name = best_label
                existing["score"] = max(existing["score"], score)

    process_nodes(raw_persons, "person")
    process_nodes(raw_orgs, "organization")

    # Sorting Order:
    # 1. Score
    # 2. Label Length
    # 3. Alphabetical
    sorted_results = sorted(
        results.values(), 
        key=lambda x: (-x["score"], len(x["label"]), x["label"].lower())
    )

    # Take the top 'limit' from the sorted results
    final_selection = sorted_results[:limit]

    return {
        "persons": [item["data"] for item in final_selection if item["category"] == "person"],
        "organizations": [item["data"] for item in final_selection if item["category"] == "organization"]
    }

def strip_uuid_hash(label: str) -> str:
    """Remove the #uuid at the end of a value."""
    return label.partition('#')[0] if label else ""

def determine_best_label(label_a: str, label_b: str) -> str:
    """Determines the most informative display name."""
    a, b = (label_a or "").strip(), (label_b or "").strip()
    
    # Prioritize labels with commas (Surname, Firstname)
    has_comma_a, has_comma_b = "," in a, "," in b
    if has_comma_a != has_comma_b:
        return a if has_comma_a else b
    
    # Return the longer name
    return a if len(a) >= len(b) else b