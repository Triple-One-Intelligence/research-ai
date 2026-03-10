"""Cypher queries for the connections service."""

PERSON_PUBLICATIONS = """
MATCH (root:RicgraphNode {value: $rootValue})-[:LINKS_TO]-(pub:RicgraphNode {name: 'DOI'})
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
MATCH (root:RicgraphNode {value: $rootValue})-[:LINKS_TO]-(pub:RicgraphNode {name: 'DOI'})
      -[:LINKS_TO]-(other:RicgraphNode {name: 'person-root'})
WHERE other <> root
  AND NOT coalesce(pub.category, '') IN $excludeCategories
WITH DISTINCT other
MATCH (other)-[:LINKS_TO]-(fn:RicgraphNode)
WHERE fn.name IN ['FULL_NAME', 'FULL_NAME_ASCII']
WITH other.value AS author_id, fn.value AS name,
     CASE
       WHEN fn.value CONTAINS ',' THEN 3
       WHEN fn.value CONTAINS ' ' THEN 2
       ELSE 1
     END AS formatScore
ORDER BY author_id, formatScore DESC, size(fn.value) DESC
WITH author_id, head(collect(name)) AS rawName
RETURN author_id, rawName
ORDER BY rawName
LIMIT $limit
"""

PERSON_ORGANIZATIONS = """
MATCH (root:RicgraphNode {value: $rootValue})-[:LINKS_TO]-(org:RicgraphNode {category: 'organization'})
WITH DISTINCT org
RETURN org.value AS organization_id, org.value AS name
ORDER BY name
LIMIT $limit
"""

ORG_MEMBERS = """
MATCH (org:RicgraphNode {value: $entityId})-[:LINKS_TO]-(root:RicgraphNode {name: 'person-root'})
MATCH (root)-[:LINKS_TO]-(fn:RicgraphNode)
WHERE fn.name IN ['FULL_NAME', 'FULL_NAME_ASCII']
WITH root.value AS author_id, fn.value AS name,
     CASE
       WHEN fn.value CONTAINS ',' THEN 3
       WHEN fn.value CONTAINS ' ' THEN 2
       ELSE 1
     END AS formatScore
ORDER BY author_id, formatScore DESC, size(fn.value) DESC
WITH author_id, head(collect(name)) AS rawName
RETURN author_id, rawName
ORDER BY rawName
LIMIT $limit
"""

ORG_PUBLICATIONS = """
MATCH (org:RicgraphNode {value: $entityId})-[:LINKS_TO]-(:RicgraphNode {name: 'person-root'})
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
MATCH (org:RicgraphNode {value: $entityId})-[:LINKS_TO]-(:RicgraphNode {name: 'person-root'})
      -[:LINKS_TO]-(other:RicgraphNode {category: 'organization'})
WHERE other <> org
WITH DISTINCT other
RETURN other.value AS organization_id, other.value AS name
ORDER BY name
LIMIT $limit
"""
