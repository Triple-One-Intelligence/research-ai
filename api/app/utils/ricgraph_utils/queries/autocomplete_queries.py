"""Cypher query for the autocomplete service."""

AUTOCOMPLETE_CYPHER = """
    CALL db.index.fulltext.queryNodes($indexName, $luceneQuery)
    YIELD node, score AS ftScore
    WHERE node.category IN ['person', 'organization']
    AND NOT node.name ENDS WITH '-root'

    // Use fulltext score for initial ordering, limit early for performance
    WITH node
    ORDER BY ftScore DESC, size(node.value) ASC
    LIMIT 1000

    // Data cleaning (uuid + leading comma)
    WITH node, trim(split(node.value, '#')[0]) AS rawClean
    WITH node, CASE WHEN rawClean STARTS WITH ',' THEN trim(substring(rawClean, 1)) ELSE rawClean END AS name

    // Clean the DB name as well for comparison
    WITH node, name,
         toLower(reduce(s = name, char IN [',','.','-'] | replace(s, char, ' '))) AS dbCleanName

    // Ensure all keywords match the actual name, not the UUID part of the value
    WHERE all(k IN $keywords WHERE dbCleanName CONTAINS k)

    WITH node, name,
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

    WITH node._key AS id, name, node.category AS type, matchScore, formatScore
    ORDER BY formatScore DESC, size(name) DESC

    WITH id, type,
         head(collect(name)) AS displayName,
         max(matchScore) AS bestScore

    // Collapse different nodes that clean to the same
    // display name (e.g. full_name vs full_name_ascii variants, or duplicate
    // source nodes). min(id) prefers |full_name over
    // |full_name_ascii since the former is smaller.
    WITH displayName, type,
         max(bestScore) AS bestScore,
         min(id) AS id

    RETURN id, displayName, type, bestScore
    ORDER BY bestScore DESC, displayName ASC
    LIMIT $limit
"""
