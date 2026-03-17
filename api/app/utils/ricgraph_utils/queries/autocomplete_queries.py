"""Cypher query for the autocomplete service."""

AUTOCOMPLETE_CYPHER = """/*cypher*/
    CALL db.index.fulltext.queryNodes($indexName, $luceneQuery)
    YIELD node, score AS ftScore
    WHERE node.category IN ['person', 'organization'] 
    AND node.name IN ['FULL_NAME', 'FULL_NAME_ASCII', 'ORGANIZATION_NAME']

    // Use fulltext score for initial ordering, limit early for performance
    WITH node, ftScore
    ORDER BY ftScore DESC, size(node.value) ASC
    LIMIT 1000

    // Data cleaning: strip UUID suffix and any leading comma from the stored value
    WITH node, trim(split(node.value, '#')[0]) AS rawClean
    // substring in Cypher is 1-based, so substring(rawClean, 1) drops the first character (the comma)
    WITH node, CASE WHEN rawClean STARTS WITH ',' THEN trim(substring(rawClean, 1)) ELSE rawClean END AS name

    // Clean the DB name for comparison: strip common punctuation to match
    // normalize_query_for_index (query_utils.py) which replaces non-word,
    // non-whitespace characters with spaces.
    WITH node, name,
         toLower(
           reduce(s = name, ch IN [',', '.', '-', '(', ')', '[', ']', '{', '}', ':', ';', '/', '\\\\', '&', '+', '!', '?', '"', "'", '#', '@'] |
             replace(s, ch, ' '))
         ) AS dbCleanName

    // Ensure all keywords match the cleaned, human-readable name (after stripping UUIDs/commas above)
    // Keep a safety net against pure technical identifiers (e.g. ORCID-style numeric IDs):
    WHERE all(k IN $keywords WHERE dbCleanName CONTAINS k)
    AND NOT name =~ '^[0-9xX-]+$'

    // Resolve person-root only for person nodes:
    // restrict the OPTIONAL MATCH to person nodes so organizations won't pick up a person-root accidentally
    OPTIONAL MATCH (node:RicgraphNode {category: 'person'})-[:LINKS_TO]-(linked:RicgraphNode {name: 'person-root'})
    WITH node, name, dbCleanName, linked,
         CASE
           // only use the linked person-root if the original node is a person
           WHEN node.category = 'person' AND linked IS NOT NULL THEN linked
           ELSE node
         END AS root

    // Compute match/format score per candidate name
    WITH node, root, name, dbCleanName,
         CASE
            WHEN dbCleanName = $cleanQuery THEN 100
            WHEN toLower(name) STARTS WITH $firstKeyword THEN 50
            ELSE 10
         END AS matchScore,
         CASE
            WHEN name CONTAINS ',' THEN 3
            WHEN name CONTAINS ' ' THEN 2
            ELSE 1
         END AS formatScore

    // For each root, pick the best displayName among its mapped nodes/names
    // Order candidates by matchScore desc, formatScore desc, size(name) desc to make selection deterministic
    WITH root, name, matchScore, formatScore
    ORDER BY matchScore DESC, formatScore DESC, size(name) DESC

    // Aggregate by root.value, keep best name and bestScore
    WITH root.value AS id, root, head(collect(name)) AS displayName, max(matchScore) AS bestScore
    WITH id, displayName, root.category AS type, bestScore

    RETURN id, displayName, type, bestScore
    ORDER BY bestScore DESC, displayName ASC
    LIMIT $limit
"""
