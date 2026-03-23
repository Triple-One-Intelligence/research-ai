import axios from 'axios';
import type { EntitySuggestion, EntityRef, ConnectionsResponse, PersonRef, OrganizationRef } from './types';

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
