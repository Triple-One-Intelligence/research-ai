export type EntityType = "person" | "organization";

export type EntityRef = {
  id: string;
  type: EntityType;
  label: string;
  extra?: string;
};

export type EntitySuggestion = EntityRef;

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
  publication_rootid?: string;
  year?: number;
  category?: string;
  name?: string;
  versions?: PublicationVersion[];
};

export type Member = {
  author_id: string;
  name: string;
  role?: string;
};

export type ConnectionsResponse = {
  entity_id: string;
  entity_type: EntityType;
  collaborators: PersonRef[];
  publications: Publication[];
  organizations: OrganizationRef[];
  members: Member[];
};
