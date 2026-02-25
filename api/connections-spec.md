# Connections Endpoint — JSON Specification

## Endpoint

```
GET /api/connections/entity?entity_id={id}&entity_type={person|organization}
```

## Response schema

```jsonc
{
  "entity_id": "string",          // echoed from query param
  "entity_type": "string",        // "person" or "organization"

  "collaborators": [              // co-authors / related persons
    {
      "author_id": "string",      // Ricgraph person _key
      "name": "string"            // display name, e.g. "Jansen, B."
    }
  ],

  "publications": [               // related publications
    {
      "doi": "string",            // required — unique identifier
      "title": "string | null",   // optional
      "publication_rootid": "string | null",
      "year": "number | null",    // e.g. 2024
      "category": "string | null",// e.g. "journal-article", "conference-paper", "report"
      "name": "string | null"     // first author name (optional)
    }
  ],

  "organizations": [              // related organizations / departments
    {
      "organization_id": "string",// Ricgraph organization _key
      "name": "string"
    }
  ],

  "members": [                    // members of an organization (empty for person entities)
    {
      "author_id": "string",
      "name": "string",
      "role": "string | null"     // optional, e.g. "Professor", "PhD Candidate"
    }
  ]
}
```

## Example — person entity

```json
{
  "entity_id": "person-1",
  "entity_type": "person",
  "collaborators": [
    { "author_id": "person-2", "name": "Jansen, B." },
    { "author_id": "person-3", "name": "De Vries, C.M." },
    { "author_id": "person-4", "name": "Van den Berg, D." }
  ],
  "publications": [
    {
      "doi": "10.1234/example-001",
      "title": "Machine Learning in Academic Research",
      "publication_rootid": null,
      "year": 2024,
      "category": "journal-article",
      "name": "Jansen, B."
    },
    {
      "doi": "10.1234/example-002",
      "title": "Graph-Based Knowledge Discovery",
      "publication_rootid": null,
      "year": 2023,
      "category": "conference-paper",
      "name": "De Vries, C.M."
    }
  ],
  "organizations": [
    { "organization_id": "org-1", "name": "Utrecht University" },
    { "organization_id": "org-2", "name": "Department of Information and Computing Sciences" }
  ],
  "members": []
}
```

## Example — organization entity

```json
{
  "entity_id": "org-1",
  "entity_type": "organization",
  "collaborators": [],
  "publications": [
    {
      "doi": "10.1234/example-004",
      "title": "Annual Report on Research Output 2024",
      "publication_rootid": null,
      "year": 2024,
      "category": "report",
      "name": null
    }
  ],
  "organizations": [
    { "organization_id": "org-3", "name": "SURF" },
    { "organization_id": "org-4", "name": "NWO" }
  ],
  "members": [
    { "author_id": "person-1", "name": "De Groot, A.", "role": "Professor" },
    { "author_id": "person-2", "name": "Jansen, B.", "role": "PhD Candidate" },
    { "author_id": "person-3", "name": "De Vries, C.M.", "role": "Postdoc" }
  ]
}
```

## Notes for backend implementer

- `doi` is the only required field on publications; all others may be `null`.
- `members` should be empty `[]` when `entity_type` is `"person"`.
- `collaborators` should be empty `[]` when `entity_type` is `"organization"` (use `members` instead).
- The frontend renders each section as a collapsible card. Sections with 0 items are hidden automatically.
- Pydantic models: `ConnectionsResponse`, `Member` in `api/app/schemas/connections.py`.
