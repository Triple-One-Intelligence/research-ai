import axios from 'axios';
import type {
  EntitySuggestion,
  EntityRef,
  ConnectionsResponse,
  PersonRef,
  OrganizationRef,
  CollaboratorsPageResponse,
  PublicationsPageResponse,
  OrganizationsPageResponse,
  MembersPageResponse,
} from './types';

// Single source of truth for the API base URL
export const API_BASE = import.meta.env.VITE_API_URL || "/api";

// Pattern: Singleton — single shared axios instance for all API calls
const api = axios.create({
  baseURL: API_BASE,
});

// Refactoring: Duplicate Code fix — PersonRef and OrganizationRef imported from types.ts
// Pattern: Adapter — transforms backend schema (author_id/organization_id) to frontend EntitySuggestion (id)
interface SuggestionsResponse {
  persons: PersonRef[];
  organizations: OrganizationRef[];
}

export const searchEntities = async (
  query: string,
  limit: number = 10
): Promise<EntitySuggestion[]> => {
  const params = new URLSearchParams();
  params.append('query', query);
  params.append('limit', limit.toString());

  const response = await api.get<SuggestionsResponse>(`/autocomplete?${params.toString()}`);

  const suggestions: EntitySuggestion[] = [];

  response.data.persons?.forEach((p) => {
    suggestions.push({
      id: p.author_id,
      type: 'person',
      label: p.name,
    });
  });

  response.data.organizations?.forEach((o) => {
    suggestions.push({
      id: o.organization_id,
      type: 'organization',
      label: o.name,
    });
  });

  return suggestions;
};

export const fetchConnections = async (
  entity: EntityRef,
  pageSize?: number
): Promise<ConnectionsResponse> => {
  const params = new URLSearchParams();
  params.append('entity_id', entity.id);
  params.append('entity_type', entity.type);

  if (pageSize != null) {
    // Request only a single page worth of each list for the initial entity load.
    params.append('max_publications', pageSize.toString());
    params.append('max_collaborators', pageSize.toString());
    params.append('max_organizations', pageSize.toString());
    params.append('max_members', pageSize.toString());
  }

  const response = await api.get<ConnectionsResponse>(
    `/connections/entity?${params.toString()}`
  );
  return response.data;
};

export const fetchCollaboratorsPage = async (
  entity: EntityRef,
  limit: number,
  cursor?: string | null,
): Promise<CollaboratorsPageResponse> => {
  const response = await fetchConnectionsPage<CollaboratorsPageResponse>(
    '/connections/collaborators',
    entity,
    limit,
    cursor
  );
  return response.data;
};

export const fetchPublicationsPage = async (
  entity: EntityRef,
  limit: number,
  cursor?: string | null,
): Promise<PublicationsPageResponse> => {
  const response = await fetchConnectionsPage<PublicationsPageResponse>(
    '/connections/publications',
    entity,
    limit,
    cursor
  );
  return response.data;
};

export const fetchOrganizationsPage = async (
  entity: EntityRef,
  limit: number,
  cursor?: string | null,
): Promise<OrganizationsPageResponse> => {
  const response = await fetchConnectionsPage<OrganizationsPageResponse>(
    '/connections/organizations',
    entity,
    limit,
    cursor
  );
  return response.data;
};

export const fetchMembersPage = async (
  entity: EntityRef,
  limit: number,
  cursor?: string | null,
): Promise<MembersPageResponse> => {
  const response = await fetchConnectionsPage<MembersPageResponse>(
    '/connections/members',
    entity,
    limit,
    cursor
  );
  return response.data;
};

const fetchConnectionsPage = <T>(
  endpoint: string,
  entity: EntityRef,
  limit: number,
  cursor?: string | null,
) => {
  const params = new URLSearchParams();
  params.append('entity_id', entity.id);
  params.append('entity_type', entity.type);
  params.append('limit', limit.toString());
  if (cursor != null) params.append('cursor', cursor);
  return api.get<T>(`${endpoint}?${params.toString()}`);
};

export default api;
