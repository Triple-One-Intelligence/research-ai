import axios from 'axios';
import type { EntitySuggestion, EntityRef, ConnectionsResponse, PersonRef, OrganizationRef } from './types';

// Shared axios instance for all API calls.
// `VITE_API_URL` can point to the dev/prod backend; we default to `/api` for local setups.
const api = axios.create({
  baseURL: import.meta.env.VITE_API_URL || "/api"
});

// Adapter for backend schemas:
// The backend returns `author_id` / `organization_id`, which we normalize into our frontend `EntitySuggestion`:
// `{ id, type, label }`.
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
  // Backend expects `limit` as a query string.
  params.append('limit', limit.toString());

  const response = await api.get<SuggestionsResponse>(`/autocomplete?${params.toString()}`);

  const suggestions: EntitySuggestion[] = [];

  // Map person results.
  response.data.persons?.forEach((p) => {
    suggestions.push({
      id: p.author_id,
      type: 'person',
      label: p.name,
    });
  });

  // Map organization results.
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
  entity: EntityRef
): Promise<ConnectionsResponse> => {
  const params = new URLSearchParams();
  params.append('entity_id', entity.id);
  params.append('entity_type', entity.type);

  const response = await api.get<ConnectionsResponse>(
    `/connections/entity?${params.toString()}`
  );
  return response.data;
};

export default api;
