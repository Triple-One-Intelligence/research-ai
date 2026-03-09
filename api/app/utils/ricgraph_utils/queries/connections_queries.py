"""Cypher queries for the connections service."""

RESOLVE_PERSON_ROOT = """
MATCH (start:RicgraphNode {_key: $entityId})
OPTIONAL MATCH (start)-[:LINKS_TO]-(linked:RicgraphNode {name: 'person-root'})
WITH CASE WHEN start.name = 'person-root' THEN start ELSE linked END AS root
WHERE root IS NOT NULL
RETURN root._key AS rootKey
LIMIT 1
"""

PERSON_PUBLICATIONS = """
MATCH (root:RicgraphNode {_key: $rootKey})-[:LINKS_TO]-(pub:RicgraphNode {name: 'DOI'})
WHERE NOT coalesce(pub.category, '') IN $excludeCategories
WITH DISTINCT pub
ORDER BY pub.year DESC
RETURN pub.value   AS doi,
       pub.comment AS title,
       pub.year    AS year,
       pub.category AS category
LIMIT $limit
"""

PERSON_COLLABORATORS = """
MATCH (root:RicgraphNode {_key: $rootKey})-[:LINKS_TO]-(pub:RicgraphNode {name: 'DOI'})
      -[:LINKS_TO]-(other:RicgraphNode {name: 'person-root'})
WHERE other <> root
  AND NOT coalesce(pub.category, '') IN $excludeCategories
WITH DISTINCT other
MATCH (other)-[:LINKS_TO]-(fn:RicgraphNode {name: 'FULL_NAME'})
WITH other._key AS author_id, head(collect(fn.value)) AS rawName
RETURN author_id, rawName
ORDER BY rawName
LIMIT $limit
"""

PERSON_ORGANIZATIONS = """
MATCH (root:RicgraphNode {_key: $rootKey})-[:LINKS_TO]-(org:RicgraphNode {category: 'organization'})
WITH DISTINCT org
RETURN org._key AS organization_id, org.value AS name
ORDER BY name
LIMIT $limit
"""

ORG_MEMBERS = """
MATCH (org:RicgraphNode {_key: $entityId})-[:LINKS_TO]-(root:RicgraphNode {name: 'person-root'})
MATCH (root)-[:LINKS_TO]-(fn:RicgraphNode {name: 'FULL_NAME'})
WITH root._key AS author_id, head(collect(fn.value)) AS rawName
RETURN author_id, rawName
ORDER BY rawName
LIMIT $limit
"""

ORG_PUBLICATIONS = """
MATCH (org:RicgraphNode {_key: $entityId})-[:LINKS_TO]-(:RicgraphNode {name: 'person-root'})
      -[:LINKS_TO]-(pub:RicgraphNode {name: 'DOI'})
WHERE NOT coalesce(pub.category, '') IN $excludeCategories
WITH DISTINCT pub
ORDER BY pub.year DESC
RETURN pub.value   AS doi,
       pub.comment AS title,
       pub.year    AS year,
       pub.category AS category
LIMIT $limit
"""

ORG_RELATED_ORGS = """
MATCH (org:RicgraphNode {_key: $entityId})-[:LINKS_TO]-(:RicgraphNode {name: 'person-root'})
      -[:LINKS_TO]-(other:RicgraphNode {category: 'organization'})
WHERE other <> org
WITH DISTINCT other
RETURN other._key AS organization_id, other.value AS name
ORDER BY name
LIMIT $limit
"""