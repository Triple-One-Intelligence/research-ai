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

export type Publication = {
  doi: string;
  title?: string;
  publication_rootid?: string;
  year?: number;
  category?: string;
  name?: string;
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

export type ChatMessage = {
  role: 'user' | 'assistant'|'system';
  content: string;
};

export type ChatResponse = {
  id?: string;
  object?: string;
  created?: number;
  model?: string;
  choices?: {
    index?: number;
    message?: {
      role?: string;
      content?: string;
    };
  }[];
  usage?: {
    prompt_tokens?: number;
    completion_tokens?: number;
    total_tokens?: number;
  };
};