"""Cypher queries for the connections service."""

PERSON_PUBLICATIONS = """/*cypher*/
// All publications linked from a person-root, excluding certain categories
MATCH (root:RicgraphNode {value: $rootValue})-[:LINKS_TO]-(pub:RicgraphNode {name: 'DOI'})
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
     END AS versions
ORDER BY representative.sortYear DESC, representative.doi ASC
RETURN representative.doi AS doi,
       representative.title AS title,
       representative.year AS year,
       representative.category AS category,
       versions AS versions
LIMIT $limit
"""

PERSON_COLLABORATORS = """/*cypher*/
// Co-authors (other person-roots) on the same publications as the given root
MATCH (root:RicgraphNode {value: $rootValue})-[:LINKS_TO]-(pub:RicgraphNode {name: 'DOI'})
      -[:LINKS_TO]-(other:RicgraphNode {name: 'person-root'})
WHERE other <> root
  AND NOT coalesce(pub.category, '') IN $excludeCategories
WITH DISTINCT other
// Resolve human-readable names for the collaborator roots
MATCH (other)-[:LINKS_TO]-(fn:RicgraphNode)
WHERE fn.name IN ['FULL_NAME', 'FULL_NAME_ASCII']
WITH other.value AS author_id, fn.value AS name,
     CASE
       WHEN fn.value CONTAINS ',' THEN 3
       WHEN fn.value CONTAINS ' ' THEN 2
       ELSE 1
     END AS formatScore
// Choose the best formatted name per collaborator
ORDER BY author_id, formatScore DESC, size(fn.value) DESC
WITH author_id, head(collect(name)) AS rawName
RETURN author_id, rawName
ORDER BY rawName
LIMIT $limit
"""

PERSON_ORGANIZATIONS = """/*cypher*/
// Organizations directly linked to the given person-root
MATCH (root:RicgraphNode {value: $rootValue})-[:LINKS_TO]-(org:RicgraphNode {category: 'organization'})
WITH DISTINCT org
RETURN org.value AS organization_id, org.value AS name
ORDER BY name
LIMIT $limit
"""

ORG_MEMBERS = """/*cypher*/
// Person-roots that are members of the given organization
MATCH (org:RicgraphNode {value: $entityId})-[:LINKS_TO]-(root:RicgraphNode {name: 'person-root'})
// Resolve human-readable names for each member
MATCH (root)-[:LINKS_TO]-(fn:RicgraphNode)
WHERE fn.name IN ['FULL_NAME', 'FULL_NAME_ASCII']
WITH root.value AS author_id, fn.value AS name,
     CASE
       WHEN fn.value CONTAINS ',' THEN 3
       WHEN fn.value CONTAINS ' ' THEN 2
       ELSE 1
     END AS formatScore
// Choose the best formatted name per member
ORDER BY author_id, formatScore DESC, size(fn.value) DESC
WITH author_id, head(collect(name)) AS rawName
RETURN author_id, rawName
ORDER BY rawName
LIMIT $limit
"""

ORG_PUBLICATIONS = """/*cypher*/
// Publications connected to the organization via its member person-roots
MATCH (org:RicgraphNode {value: $entityId})-[:LINKS_TO]-(:RicgraphNode {name: 'person-root'})
      -[:LINKS_TO]-(pub:RicgraphNode {name: 'DOI'})
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
     END AS versions
ORDER BY representative.sortYear DESC, representative.doi ASC
RETURN representative.doi AS doi,
       representative.title AS title,
       representative.year AS year,
       representative.category AS category,
       versions AS versions
LIMIT $limit
"""

ORG_RELATED_ORGS = """/*cypher*/
// Other organizations sharing person-roots with the given organization
MATCH (org:RicgraphNode {value: $entityId})-[:LINKS_TO]-(:RicgraphNode {name: 'person-root'})
      -[:LINKS_TO]-(other:RicgraphNode {category: 'organization'})
WHERE other <> org
WITH DISTINCT other
RETURN other.value AS organization_id, other.value AS name
ORDER BY name
LIMIT $limit
"""
