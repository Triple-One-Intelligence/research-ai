"""
Includes helper functions which aid with making queries to the neo4j database
"""
import re

# Lucene reserved characters that must be escaped
LUCENE_SPECIAL = re.compile(r'([+\-&|!(){}\[\]^"~*?:\\/])')

def escape_lucene(term: str) -> str:
    """Escape Lucene special characters in a search term."""
    return LUCENE_SPECIAL.sub(r'\\\1', term)

def build_lucene_query(keywords: list[str]) -> str:
    """
    Build a Lucene query string for autocomplete.

    Every keyword gets a wildcard suffix so partial input matches.
    All keywords are AND-joined so every term must be present.

    Example: ["henk", "boer"] -> "henk* AND boer*"
    """
    parts = [f"{escape_lucene(keyword)}*" for keyword in keywords]
    return " AND ".join(parts)

def normalize_query_for_index(user_query: str):
    """
    Tokenization alignment: the fulltext index analyzer splits on
    punctuation, so we do the same to ensure each keyword maps to an
    indexed token.
    """
    return re.sub(r'[^\w\s]', ' ', user_query)
