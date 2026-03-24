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

# Get the top K colleagues for a selected user. 
# Final score based on:
#   how many publications they worked on together, 
#   whether or not they work at the same intitute,
#   How much overlap their remaining publications has with the ones from the original target entity (vcector comparison) 
# Finaly ranked in descending order
get_TOPK_COLLEAGUES = """
    MATCH (target:RicgraphNode {name: "person-root", value: $target_person_id})

    // Get all colleagues (coauthors + org mates)
    OPTIONAL MATCH (target)-[:LINKS_TO]->(pub:RicgraphNode {name: "DOI"})-[:LINKS_TO]->(coauthor:RicgraphNode {name: "person-root"})
    WHERE coauthor.value <> target.value

    OPTIONAL MATCH (target)-[:LINKS_TO]->(org:RicgraphNode {name: "ORGANIZATION_NAME"})-[:LINKS_TO]->(orgmate:RicgraphNode {name: "person-root"})
    WHERE orgmate.value <> target.value

    WITH target, COLLECT(DISTINCT coauthor) + COLLECT(DISTINCT orgmate) AS all_colleagues
    UNWIND all_colleagues AS colleague

    // Papers together
    OPTIONAL MATCH (target)-[:LINKS_TO]->(shared_pub:RicgraphNode {name: "DOI"})-[:LINKS_TO]->(colleague)
    WITH target, colleague, COUNT(DISTINCT shared_pub) AS papers_together, COLLECT(DISTINCT shared_pub) AS shared_pubs

    // Target's other publications (excluding cowritten)
    OPTIONAL MATCH (target)-[:LINKS_TO]->(target_pub:RicgraphNode {name: "DOI"})
    WHERE NOT target_pub IN shared_pubs
    WITH target, colleague, papers_together, shared_pubs, COLLECT(target_pub.embedding) AS target_embeddings

    // Colleague's other publications (excluding cowritten)
    OPTIONAL MATCH (colleague)-[:LINKS_TO]->(colleague_pub:RicgraphNode {name: "DOI"})
    WHERE NOT colleague_pub IN shared_pubs
    WITH target, colleague, papers_together, target_embeddings, COLLECT(colleague_pub.embedding) AS colleague_embeddings

    // Handle case where colleague has no other publications
    WITH target, colleague, papers_together, target_embeddings, colleague_embeddings,
        CASE 
        WHEN size(target_embeddings) = 0 OR size(colleague_embeddings) = 0 THEN 0.0
        ELSE null  // marker to calculate similarity
        END AS early_exit_score

    // If early_exit_score is not null, use it; otherwise calculate
    WITH target, colleague, papers_together, target_embeddings, colleague_embeddings, early_exit_score,
        CASE 
        WHEN early_exit_score IS NOT NULL THEN early_exit_score
        ELSE (
            // Calculate magnitudes for target embeddings
            [t_emb IN target_embeddings | 
            {
                embedding: t_emb,
                magnitude: sqrt(reduce(sum = 0.0, i IN range(0, size(t_emb) - 1) | sum + t_emb[i] * t_emb[i]))
            }
            ]  // Get first for now
        )
        END AS placeholder

    // Calculate dot product and magnitudes for each target embedding
    WITH target, colleague, papers_together, target_embeddings, colleague_embeddings, early_exit_score,
        [t_emb IN target_embeddings | 
        {
            embedding: t_emb,
            magnitude: sqrt(reduce(sum = 0.0, i IN range(0, size(t_emb) - 1) | sum + t_emb[i] * t_emb[i]))
        }
        ] AS target_emb_data

    // Calculate dot product and magnitudes for each colleague embedding
    WITH target, colleague, papers_together, target_emb_data, colleague_embeddings, early_exit_score,
        [c_emb IN colleague_embeddings | 
        {
            embedding: c_emb,
            magnitude: sqrt(reduce(sum = 0.0, i IN range(0, size(c_emb) - 1) | sum + c_emb[i] * c_emb[i]))
        }
        ] AS colleague_emb_data

    // Calculate best embedding overlap
    WITH target, colleague, papers_together, early_exit_score,
        CASE 
        WHEN early_exit_score IS NOT NULL THEN early_exit_score
        ELSE (
            // Calculate all pairwise similarities
            CASE 
            WHEN size(target_emb_data) > 0 AND size(colleague_emb_data) > 0 THEN
                reduce(max_sim = 0.0, t_data IN target_emb_data |
                reduce(current_max = max_sim, c_data IN colleague_emb_data |
                    CASE 
                    WHEN t_data.magnitude = 0 OR c_data.magnitude = 0 THEN current_max
                    ELSE CASE 
                        WHEN (reduce(sum = 0.0, i IN range(0, size(t_data.embedding) - 1) | 
                        sum + t_data.embedding[i] * c_data.embedding[i]) / (t_data.magnitude * c_data.magnitude)) > current_max
                        THEN (reduce(sum = 0.0, i IN range(0, size(t_data.embedding) - 1) | 
                        sum + t_data.embedding[i] * c_data.embedding[i]) / (t_data.magnitude * c_data.magnitude))
                        ELSE current_max
                    END
                    END
                )
                )
            ELSE 0.0
            END
        )
        END AS best_embedding_overlap

    // Same organisation
    OPTIONAL MATCH (target)-[:LINKS_TO]->(shared_org:RicgraphNode {name: "ORGANIZATION_NAME"})-[:LINKS_TO]->(colleague)
    WITH target, colleague, papers_together, best_embedding_overlap, COUNT(shared_org) > 0 AS same_org

    // Get colleague name
    OPTIONAL MATCH (colleague)-[:LINKS_TO]->(name:RicgraphNode {name: "FULL_NAME"})

    // Calculate final score
    WITH colleague.value AS colleague_id,
        name.value AS colleague_name,
        papers_together,
        same_org,
        COALESCE(best_embedding_overlap, 0.0) AS best_embedding_overlap,
        (
        (CASE WHEN papers_together > 0 THEN CASE WHEN papers_together / 5.0 > 1.0 THEN 1.0 ELSE papers_together / 5.0 END ELSE 0.0 END) * 0.5 +
        (CASE WHEN same_org THEN 1.0 ELSE 0.0 END) * 0.3 +
        COALESCE(best_embedding_overlap, 0.0) * 0.2
        ) AS final_score

    RETURN 
    colleague_id,
    colleague_name,
    papers_together,
    same_org,
    ROUND(best_embedding_overlap, 3) AS best_embedding_overlap,
    ROUND(final_score, 3) AS final_score
    ORDER BY final_score DESC
    LIMIT $top_k
"""