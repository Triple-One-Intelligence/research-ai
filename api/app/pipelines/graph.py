"""
Neo4j queries for pipeline context — ranked by shared publication count, unlike the display queries in connections_queries.py.
"""
from app.utils.database_utils.database_utils import get_graph
from app.utils.ricgraph_utils.connections_utils import EXCLUDE_CATEGORIES

_PERSON_COLLABORATORS_RANKED = """
MATCH (root:RicgraphNode {value: $rootValue})-[:LINKS_TO]-(pub:RicgraphNode {name: 'DOI'})
      -[:LINKS_TO]-(other:RicgraphNode {name: 'person-root'})
WHERE other <> root
  AND NOT coalesce(pub.category, '') IN $excludeCategories
WITH other, count(DISTINCT pub) AS sharedPubs
MATCH (other)-[:LINKS_TO]-(fn:RicgraphNode)
WHERE fn.name IN ['FULL_NAME', 'FULL_NAME_ASCII']
WITH other.value AS author_id, fn.value AS name, sharedPubs,
     CASE
       WHEN fn.value CONTAINS ',' THEN 3
       WHEN fn.value CONTAINS ' ' THEN 2
       ELSE 1
     END AS formatScore
ORDER BY author_id, formatScore DESC, size(fn.value) DESC
WITH author_id, head(collect(name)) AS rawName, sharedPubs
RETURN author_id, rawName, sharedPubs
ORDER BY sharedPubs DESC, rawName
LIMIT $limit
"""

# Traverses co-authors to find their orgs, excluding the person's own organizations.
_PERSON_COLLAB_ORGANIZATIONS = """
MATCH (root:RicgraphNode {value: $rootValue})
OPTIONAL MATCH (root)-[:LINKS_TO]-(own_org:RicgraphNode {category: 'organization'})
WITH root, collect(own_org) AS own_orgs
MATCH (root)-[:LINKS_TO]-(pub:RicgraphNode {name: 'DOI'})
      -[:LINKS_TO]-(other:RicgraphNode {name: 'person-root'})
      -[:LINKS_TO]-(org:RicgraphNode {category: 'organization'})
WHERE other <> root
  AND NOT org IN own_orgs
  AND NOT coalesce(pub.category, '') IN $excludeCategories
WITH DISTINCT org, count(DISTINCT pub) AS sharedPubs
RETURN org.value AS name, sharedPubs
ORDER BY sharedPubs DESC
LIMIT $limit
"""

_ORG_RELATED_ORGS_RANKED = """
MATCH (org:RicgraphNode {value: $entityId})
      -[:LINKS_TO]-(root:RicgraphNode {name: 'person-root'})
      -[:LINKS_TO]-(other:RicgraphNode {category: 'organization'})
WHERE other <> org
WITH DISTINCT other, count(DISTINCT root) AS sharedMembers
RETURN other.value AS name, sharedMembers
ORDER BY sharedMembers DESC
LIMIT $limit
"""

_ORG_EXTERNAL_COLLABORATORS_RANKED = """
MATCH (org:RicgraphNode {value: $entityId})
      -[:LINKS_TO]-(member:RicgraphNode {name: 'person-root'})
      -[:LINKS_TO]-(pub:RicgraphNode {name: 'DOI'})
      -[:LINKS_TO]-(other:RicgraphNode {name: 'person-root'})
WHERE other <> member
  AND NOT (org)-[:LINKS_TO]-(other)
  AND NOT coalesce(pub.category, '') IN $excludeCategories
WITH other, count(DISTINCT pub) AS sharedPubs
MATCH (other)-[:LINKS_TO]-(fn:RicgraphNode)
WHERE fn.name IN ['FULL_NAME', 'FULL_NAME_ASCII']
WITH other.value AS author_id, fn.value AS name, sharedPubs,
     CASE
       WHEN fn.value CONTAINS ',' THEN 3
       WHEN fn.value CONTAINS ' ' THEN 2
       ELSE 1
     END AS formatScore
ORDER BY author_id, formatScore DESC, size(fn.value) DESC
WITH author_id, head(collect(name)) AS rawName, sharedPubs
RETURN author_id, rawName, sharedPubs
ORDER BY sharedPubs DESC, rawName
LIMIT $limit
"""

_ABSTRACTS_BY_DOI = """
MATCH (pub:RicgraphNode {name: 'DOI'})
WHERE pub.value IN $dois AND pub.abstract IS NOT NULL
RETURN pub.value AS doi, pub.abstract AS abstract
"""


def fetch_abstracts(dois: list[str]) -> dict[str, str]:
    if not dois:
        return {}
    with get_graph().session() as session:
        return {r["doi"]: r["abstract"] for r in session.run(_ABSTRACTS_BY_DOI, dois=dois)}


def person_collaborators_ranked(entity_id: str, limit: int) -> list[dict]:
    with get_graph().session() as session:
        return session.run(
            _PERSON_COLLABORATORS_RANKED,
            rootValue=entity_id,
            excludeCategories=EXCLUDE_CATEGORIES,
            limit=limit,
        ).data()


def person_collab_organizations(entity_id: str, limit: int) -> list[dict]:
    with get_graph().session() as session:
        return session.run(
            _PERSON_COLLAB_ORGANIZATIONS,
            rootValue=entity_id,
            excludeCategories=EXCLUDE_CATEGORIES,
            limit=limit,
        ).data()


def org_external_collaborators_ranked(entity_id: str, limit: int) -> list[dict]:
    with get_graph().session() as session:
        return session.run(
            _ORG_EXTERNAL_COLLABORATORS_RANKED,
            entityId=entity_id,
            excludeCategories=EXCLUDE_CATEGORIES,
            limit=limit,
        ).data()


def org_related_orgs_ranked(entity_id: str, limit: int) -> list[dict]:
    with get_graph().session() as session:
        return session.run(
            _ORG_RELATED_ORGS_RANKED,
            entityId=entity_id,
            limit=limit,
        ).data()
