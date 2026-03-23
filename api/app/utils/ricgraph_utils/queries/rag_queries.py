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
       pub.abstract AS abstract,
       score
ORDER BY score DESC
"""

# Vector search scoped to a person entity's publications
PERSON_SIMILAR_PUBLICATIONS = """
CALL db.index.vector.queryNodes($indexName, $searchK, $prompt_embedding)
YIELD node AS pub, score
MATCH (start:RicgraphNode {value: $entityId})
OPTIONAL MATCH (start)-[:LINKS_TO]-(pr:RicgraphNode {name: 'person-root'})
WITH pub, score,
     CASE WHEN start.name = 'person-root' THEN start ELSE pr END AS root
WHERE root IS NOT NULL AND EXISTS { (root)-[:LINKS_TO]-(pub) }
RETURN pub.value    AS doi,
       pub.comment  AS title,
       pub.year     AS year,
       pub.category AS category,
       pub.abstract AS abstract,
       score
ORDER BY score DESC
LIMIT $limit
"""

# Vector search scoped to an organization's publications
ORG_SIMILAR_PUBLICATIONS = """
CALL db.index.vector.queryNodes($indexName, $searchK, $prompt_embedding)
YIELD node AS pub, score
WHERE EXISTS {
  MATCH (org:RicgraphNode {value: $entityId})
        -[:LINKS_TO]-(:RicgraphNode {name: 'person-root'})
        -[:LINKS_TO]-(pub)
}
RETURN DISTINCT
       pub.value    AS doi,
       pub.comment  AS title,
       pub.year     AS year,
       pub.category AS category,
       pub.abstract AS abstract,
       score
ORDER BY score DESC
LIMIT $limit
"""

#Takes (rootValue: str, limit: int)
get_PERSON_PUBLICATIONS = """/*cypher*/
// All publications linked from a person-root, excluding certain categories
MATCH (root:RicgraphNode {value: $entityId})-[:LINKS_TO]-(pub:RicgraphNode {name: 'DOI'})
WITH DISTINCT pub
ORDER BY pub.year DESC
RETURN pub.value   AS doi,
       pub.comment AS title,
       pub.year    AS year,
       pub.category AS category,
       pub.abstract AS abstract
LIMIT $limit
"""

get_ORG_PUBLICATIONS = """/*cypher*/
// Publications connected to the organization via its member person-roots
MATCH (org:RicgraphNode {value: $entityId})-[:LINKS_TO]-(:RicgraphNode {name: 'person-root'})
      -[:LINKS_TO]-(pub:RicgraphNode {name: 'DOI'})
WITH DISTINCT pub
ORDER BY pub.year DESC
RETURN pub.value   AS doi,
       pub.comment AS title,
       pub.year    AS year,
       pub.category AS category,
       pub.abstract AS abstract
LIMIT $limit
"""