# Connections Endpoint — JSON Specification

## Endpoint

```
GET /api/connections/entity
```

**Query parameters**

| Parameter           | Type   | Required | Default | Constraints  | Description |
|---------------------|--------|----------|---------|--------------|-------------|
| `entity_id`         | string | yes      | —       | —            | ID of the entity (Ricgraph person or organization key). |
| `entity_type`       | string | yes      | —       | `person` or `organization` | Type of the entity. |
| `max_publications`  | int    | no       | 50      | 1–200        | Maximum number of publications to return. |
| `max_collaborators` | int    | no       | 50      | 1–200        | Maximum number of collaborators to return (person only). |
| `max_organizations` | int    | no       | 50      | 1–200        | Maximum number of organizations to return. |
| `max_members`       | int    | no       | 50      | 1–200        | Maximum number of members to return (organization only). |

**Error responses**

- **400** — `entity_type` is not `person` or `organization` (message from `InvalidEntityTypeError`).
- **500** — Database or internal error (`ConnectionsError` or unhandled exception); detail: `"Connections query failed"`.

## Response schema

```jsonc
{
  "entity_id": "string",          // echoed from query param
  "entity_type": "string",        // "person" or "organization"

  "collaborators": [              // co-authors / related persons (empty for organization)
    {
      "author_id": "string",      // Ricgraph person _key
      "name": "string"            // display name, e.g. "Jansen, B."
    }
  ],

  "publications": [               // related publications
    {
      "doi": "string",            // required — unique identifier
      "title": "string | null",   // optional
      "year": "number | null",    // e.g. 2024
      "category": "string | null",// e.g. "journal-article", "conference-paper", "report"
      "versions": [               // optional; present when multiple versions (same title) are merged
        { "doi": "string", "year": "number | null", "category": "string | null" }
      ]
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
      "name": "string"
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
      "year": 2024,
      "category": "journal-article",
      "versions": null
    },
    {
      "doi": "10.1234/example-002",
      "title": "Graph-Based Knowledge Discovery",
      "year": 2023,
      "category": "conference-paper",
      "versions": null
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
      "year": 2024,
      "category": "report",
      "versions": null
    }
  ],
  "organizations": [
    { "organization_id": "org-3", "name": "SURF" },
    { "organization_id": "org-4", "name": "NWO" }
  ],
  "members": [
    { "author_id": "person-1", "name": "De Groot, A." },
    { "author_id": "person-2", "name": "Jansen, B." },
    { "author_id": "person-3", "name": "De Vries, C.M." }
  ]
}
```

## Endpoint — collaborators

```
GET /api/connections/collaborators
```

**Query parameters**

| Parameter           | Type   | Required | Default | Constraints  | Description |
|---------------------|--------|----------|---------|--------------|-------------|
| `entity_id`         | string | yes      | —       | —            | ID of the entity (Ricgraph person or organization key). |
| `entity_type`       | string | yes      | —       | `person` or `organization` | Type of the entity. |
| `limit`             | int    | no       | 50      | 1–200        | Maximum number of collaborators to return. |
| `cursor`            | string | no       | —       | —            | Pagination cursor (ignored for now). |

## Response schema

```json
{
  "entity_id": "string",
  "entity_type": "string",
  "collaborators": [
    { "author_id": "string", "name": "string" }
  ],
  "next_cursor": "string | null"
}
```

## Endpoint — publications

```
GET /api/connections/publications
```

**Query parameters**

| Parameter           | Type   | Required | Default | Constraints  | Description |
|---------------------|--------|----------|---------|--------------|-------------|
| `entity_id`         | string | yes      | —       | —            | ID of the entity (Ricgraph person or organization key). |
| `entity_type`       | string | yes      | —       | `person` or `organization` | Type of the entity. |
| `limit`             | int    | no       | 50      | 1–200        | Maximum number of publications to return. |
| `cursor`            | string | no       | —       | —            | Pagination cursor (ignored for now). |

## Response schema

```json
{
  "entity_id": "string",
  "entity_type": "string",
  "publications": [
    { "doi": "string", "title": "string | null", "year": "number | null", "category": "string | null", "versions": [] }
  ],
  "next_cursor": "string | null"
}
```

## Endpoint — organizations

```
GET /api/connections/organizations
```

**Query parameters**

| Parameter            | Type   | Required | Default | Constraints  | Description |
|----------------------|--------|----------|---------|--------------|-------------|
| `entity_id`          | string | yes      | —       | —            | ID of the entity (Ricgraph person or organization key). |
| `entity_type`        | string | yes      | —       | `person` or `organization` | Type of the entity. |
| `limit`              | int    | no       | 50      | 1–200        | Maximum number of organizations to return. |
| `cursor`             | string | no       | —       | —            | Pagination cursor (ignored for now). |

## Response schema

```json
{
  "entity_id": "string",
  "entity_type": "string",
  "organizations": [
    { "organization_id": "string", "name": "string" }
  ],
  "next_cursor": "string | null"
}
```

## Endpoint — members

```
GET /api/connections/members
```

**Query parameters**

| Parameter         | Type   | Required | Default | Constraints  | Description |
|-------------------|--------|----------|---------|--------------|-------------|
| `entity_id`       | string | yes      | —       | —            | ID of the entity (Ricgraph person or organization key). |
| `entity_type`     | string | yes      | —       | `person` or `organization` | Type of the entity. |
| `limit`            | int    | no       | 50      | 1–200        | Maximum number of members to return. |
| `cursor`           | string | no       | —       | —            | Pagination cursor (ignored for now). |

## Response schema

```json
{
  "entity_id": "string",
  "entity_type": "string",
  "members": [
    { "author_id": "string", "name": "string" }
  ],
  "next_cursor": "string | null"
}
```

## Notes for backend implementer

- `doi` is the only required field on publications; `title`, `year`, `category`, and `versions` may be null or omitted.
- Publications with the same normalized title are deduplicated; when multiple versions exist, the first is kept and the rest are listed in `versions` (each with `doi`, `year`, `category`). See `format_publications` in `api/app/utils/ricgraph_utils/connections_utils.py`.
- `members` is always `[]` when `entity_type` is `"person"`.
- `collaborators` is always `[]` when `entity_type` is `"organization"` (use `members` for organization personnel).
- The frontend renders each section as a collapsible card. Sections with 0 items are hidden automatically.
- **Pydantic models**: `Connections`, `Member` in `api/app/utils/schemas/connections.py`; `Person`, `Publication`, `Organization` in `api/app/utils/schemas/` (person.py, publication.py, organization.py).
- **Router**: `api/app/routers/connections.py` (prefix `/connections`). App is mounted with `root_path="/api"`, so full path is `/api/connections/entity`.
