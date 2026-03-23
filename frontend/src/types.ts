export type EntityType = "person" | "organization";

// Normalized frontend representation for a backend entity.
// - `id` is the backend identifier (author_id / organization_id)
// - `type` tells us which identifier field it came from
// - `label` is what we show in the UI
export type EntityRef = {
  id: string;
  type: EntityType;
  label: string;
  extra?: string;
};

// Currently identical to `EntityRef`, but kept as a separate semantic alias
// because "suggestions" may eventually carry additional UI-only metadata.
export type EntitySuggestion = EntityRef;

// Reserved for future use
export type YearRange = { from: number; to: number };

export type PromptTemplate = {
  id: string;
  title: string;
  icon?: string;
  entityTypes: EntityType[];
  intent?: string;
  description?: string;
};

// --- Connections response types ---

export type PersonRef = {
  author_id: string;
  name: string;
};

export type OrganizationRef = {
  organization_id: string;
  name: string;
};

export type PublicationVersion = {
  doi: string;
  year?: number;
  category?: string;
};

export type Publication = {
  doi: string;
  title?: string;
  year?: number;
  category?: string;
  versions?: PublicationVersion[];
};

export type Member = {
  author_id: string;
  name: string;
};

export type ConnectionsResponse = {
  entity_id: string;
  entity_type: EntityType;
  collaborators: PersonRef[];
  publications: Publication[];
  organizations: OrganizationRef[];
  members: Member[];
};
