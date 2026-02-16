
import axios from 'axios';
import type { EntitySuggestion } from './types';

const api = axios.create({
  baseURL: import.meta.env.VITE_API_URL || "/api"  
});

// Backend response types
interface Person {
  author_id: string;
  name: string;
}

interface Organization {
  organization_id: string;
  name: string;
}

interface SuggestionsResponse {
  persons: Person[];
  organizations: Organization[];  
}

export const searchEntities = async (
  query: string,
  limit: number = 10
): Promise<EntitySuggestion[]> => {
  const params = new URLSearchParams();
  params.append('query', query);
  params.append('limit', limit.toString());
 

  const response = await api.get<SuggestionsResponse>(`/autocomplete/?${params.toString()}`);
  
  // Transform backend response to frontend type EntitySuggestion[]
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

export default api;
