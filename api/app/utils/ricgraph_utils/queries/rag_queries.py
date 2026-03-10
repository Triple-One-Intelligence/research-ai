SIMILAR_PUBLICATIONS = """
CALL db.index.vector.queryNodes(
  $indexName,
  $k,
  $prompt_embedding
)
YIELD node AS pub, score
RETURN pub.value   AS doi,
       pub.comment AS title,
       pub.year    AS year,
       pub.category AS category
       pub.abstract AS abstract
ORDER BY score DESC
"""