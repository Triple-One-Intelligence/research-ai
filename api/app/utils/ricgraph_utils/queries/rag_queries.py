SIMILAR_PUBLICATIONS = """
CALL db.index.vector.queryNodes(
  $indexName,
  $k,
  $prompt_embedding
)
YIELD node AS pub, score
RETURN pub.value    AS doi,
       pub.comment  AS title,
       pub.year     AS year,
       pub.category AS category,
       pub.abstract AS abstract
ORDER BY score DESC
"""

# Get publications for a person entity (via person-root), including abstracts
PERSON_PUBLICATIONS_WITH_ABSTRACT = """
MATCH (start:RicgraphNode {_key: $entityId})
OPTIONAL MATCH (start)-[:LINKS_TO]-(linked:RicgraphNode {name: 'person-root'})
WITH CASE WHEN start.name = 'person-root' THEN start ELSE linked END AS root
WHERE root IS NOT NULL
MATCH (root)-[:LINKS_TO]-(pub:RicgraphNode {name: 'DOI'})
WHERE pub.abstract IS NOT NULL
WITH DISTINCT pub
ORDER BY pub.year DESC
RETURN pub.value    AS doi,
       pub.comment  AS title,
       pub.year     AS year,
       pub.category AS category,
       pub.abstract AS abstract
LIMIT $limit
"""

# Get publications for an organization entity, including abstracts
ORG_PUBLICATIONS_WITH_ABSTRACT = """
MATCH (org:RicgraphNode {_key: $entityId})
      -[:LINKS_TO]-(:RicgraphNode {name: 'person-root'})
      -[:LINKS_TO]-(pub:RicgraphNode {name: 'DOI'})
WHERE pub.abstract IS NOT NULL
WITH DISTINCT pub
ORDER BY pub.year DESC
RETURN pub.value    AS doi,
       pub.comment  AS title,
       pub.year     AS year,
       pub.category AS category,
       pub.abstract AS abstract
LIMIT $limit
"""
