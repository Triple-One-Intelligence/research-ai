from pydantic import BaseModel
from typing import Any, Dict, List, Optional

class Publication(BaseModel):
    """
    a publication can be many things (e.g. journal article, report, review, etc.), but it always has a unique DOI
    """
    doi: str
    title: Optional[str] = None
    publication_rootid: Optional[str] = None
    year: Optional[int] = None
    category: Optional[str] = None
    name: Optional[str] = None
    versions: Optional[List[Dict[str, Any]]] = None
