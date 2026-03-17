from typing import Any

from pydantic import BaseModel


class Publication(BaseModel):
    """
    a publication can be many things (e.g. journal article, report, review, etc.), but it always has a unique DOI
    """
    doi: str
    title: str | None = None
    year: int | None = None
    category: str | None = None
    versions: list[dict[str, Any]] | None = None
