"""Cypher queries for the connections service."""

PEOPLE_NAME_SELECTION_AND_CURSOR = """
// Resolve human-readable names for each person-root
MATCH (personNode)-[:LINKS_TO]-(fn:RicgraphNode)
WHERE fn.name IN ['FULL_NAME', 'FULL_NAME_ASCII']
WITH personNode.value AS author_id, fn.value AS name,
     CASE
       WHEN fn.value CONTAINS ',' THEN 3
       WHEN fn.value CONTAINS ' ' THEN 2
       ELSE 1
     END AS formatScore
// Choose the best formatted name per person-root
ORDER BY author_id, formatScore DESC, size(fn.value) DESC, fn.value ASC
WITH author_id, head(collect(name)) AS rawName
WITH author_id, rawName, toLower(trim(coalesce(rawName, ''))) AS baseSortName
WITH author_id, rawName,
     CASE
       WHEN baseSortName STARTS WITH "'" THEN substring(baseSortName, 1)
       ELSE baseSortName
     END AS sortName
WHERE $cursorName IS NULL
   OR sortName > $cursorName
   OR (sortName = $cursorName AND author_id > $cursorAuthorId)
RETURN author_id, rawName, sortName AS sort_name
ORDER BY sortName, author_id
LIMIT $limit
"""

PUBLICATIONS_QUERY_BODY = """
WHERE NOT coalesce(pub.category, '') IN $excludeCategories
WITH DISTINCT pub,
     trim(coalesce(pub.comment, '')) AS normalizedTitle,
     coalesce(toInteger(pub.year), -1) AS sortYear
WITH pub,
     sortYear,
     CASE
       WHEN normalizedTitle = '' THEN 'doi:' + pub.value
       ELSE 'title:' + toLower(normalizedTitle)
     END AS publicationKey
ORDER BY publicationKey, sortYear DESC, pub.value ASC
WITH publicationKey, collect({
       doi: pub.value,
       title: pub.comment,
       year: pub.year,
       category: pub.category,
       sortYear: sortYear
     }) AS entries
WITH entries, head(entries) AS representative
WITH representative, entries,
     CASE WHEN size(entries) > 1
          THEN [entry IN entries | {doi: entry.doi, year: entry.year, category: entry.category}]
          ELSE null
     END AS versions,
     CASE
       WHEN trim(coalesce(representative.title, '')) = '' THEN 'doi:' + representative.doi
       ELSE 'title:' + toLower(trim(representative.title))
     END AS publicationSortKey
WHERE $cursorKey IS NULL
   OR publicationSortKey > $cursorKey
   OR (publicationSortKey = $cursorKey AND representative.doi > $cursorDoi)
ORDER BY publicationSortKey ASC, representative.doi ASC
RETURN representative.doi AS doi,
       representative.title AS title,
       representative.year AS year,
       representative.category AS category,
       versions AS versions
LIMIT $limit
"""

PERSON_PUBLICATIONS = """/*cypher*/
// All publications linked from a person-root, excluding certain categories
MATCH (root:RicgraphNode {value: $rootValue})-[:LINKS_TO]-(pub:RicgraphNode {name: 'DOI'})
""" + PUBLICATIONS_QUERY_BODY

PERSON_COLLABORATORS = """/*cypher*/
// Co-authors (other person-roots) on the same publications as the given root
MATCH (root:RicgraphNode {value: $rootValue})-[:LINKS_TO]-(pub:RicgraphNode {name: 'DOI'})
      -[:LINKS_TO]-(other:RicgraphNode {name: 'person-root'})
WHERE other <> root
  AND NOT coalesce(pub.category, '') IN $excludeCategories
WITH DISTINCT other AS personNode
""" + PEOPLE_NAME_SELECTION_AND_CURSOR

PERSON_ORGANIZATIONS = """/*cypher*/
// Organizations directly linked to the given person-root
MATCH (root:RicgraphNode {value: $rootValue})-[:LINKS_TO]-(org:RicgraphNode {category: 'organization'})
WITH DISTINCT org
WITH org, toLower(org.value) AS sortName
WHERE $cursorName IS NULL
   OR sortName > $cursorName
   OR (sortName = $cursorName AND org.value > $cursorOrganizationId)
RETURN org.value AS organization_id, org.value AS name
ORDER BY sortName, organization_id
LIMIT $limit
"""

ORG_MEMBERS = """/*cypher*/
// Person-roots that are members of the given organization
MATCH (org:RicgraphNode {value: $entityId})-[:LINKS_TO]-(root:RicgraphNode {name: 'person-root'})
WITH DISTINCT root AS personNode
""" + PEOPLE_NAME_SELECTION_AND_CURSOR

ORG_PUBLICATIONS = """/*cypher*/
// Publications connected to the organization via its member person-roots
MATCH (org:RicgraphNode {value: $entityId})-[:LINKS_TO]-(:RicgraphNode {name: 'person-root'})
      -[:LINKS_TO]-(pub:RicgraphNode {name: 'DOI'})
""" + PUBLICATIONS_QUERY_BODY

ORG_RELATED_ORGS = """/*cypher*/
// Other organizations sharing person-roots with the given organization
MATCH (org:RicgraphNode {value: $entityId})-[:LINKS_TO]-(:RicgraphNode {name: 'person-root'})
      -[:LINKS_TO]-(other:RicgraphNode {category: 'organization'})
WHERE other <> org
WITH DISTINCT other
WITH other, toLower(other.value) AS sortName
WHERE $cursorName IS NULL
   OR sortName > $cursorName
   OR (sortName = $cursorName AND other.value > $cursorOrganizationId)
RETURN other.value AS organization_id, other.value AS name
ORDER BY sortName, organization_id
LIMIT $limit
"""
