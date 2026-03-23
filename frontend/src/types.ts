export type EntityType = "person" | "organization";

export type EntityRef = {
  id: string;
  type: EntityType;
  label: string;
  extra?: string;
};

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
  collaborators_cursor: string | null;
  publications_cursor: string | null;
  organizations_cursor: string | null;
  members_cursor: string | null;
};

// --- Per-type paginated responses (cursor pagination skeleton) ---

export type CollaboratorsPageResponse = {
  entity_id: string;
  entity_type: EntityType;
  collaborators: PersonRef[];
  cursor: string | null;
};

export type PublicationsPageResponse = {
  entity_id: string;
  entity_type: EntityType;
  publications: Publication[];
  cursor: string | null;
};

export type OrganizationsPageResponse = {
  entity_id: string;
  entity_type: EntityType;
  organizations: OrganizationRef[];
  cursor: string | null;
};

export type MembersPageResponse = {
  entity_id: string;
  entity_type: EntityType;
  members: Member[];
  cursor: string | null;
};
