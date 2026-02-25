
import axios from 'axios';
import type { EntitySuggestion, EntityRef, ConnectionsResponse } from './types';

const DEFAULT_MODEL_REPO = 'Qwen/Qwen2.5-0.5B-Instruct-GGUF';
const DEFAULT_MODEL_FILE = '*q8_0.gguf';

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
 

  const response = await api.get<SuggestionsResponse>(`/autocomplete?${params.toString()}`);
  
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

export const sendChat = async (prompt: string): Promise<string> => {
  const response = await api.post<{ text: string }>('/ai/chat', {
    repo_id: DEFAULT_MODEL_REPO,
    filename: DEFAULT_MODEL_FILE,
    prompt,
  });
  return response.data.text;
};

export const buildContextPrompt = (
  entity: EntityRef,
  connections: ConnectionsResponse | null,
  question: string,
): string => {
  let context = `Entity: ${entity.label} (${entity.type})\n\n`;

  if (connections) {
    if (connections.publications.length > 0) {
      context += `Publications (${connections.publications.length}):\n`;
      connections.publications.slice(0, 10).forEach((p) => {
        context += `- ${p.title ?? p.doi}${p.year ? ` (${p.year})` : ''}\n`;
      });
      context += '\n';
    }
    if (connections.collaborators.length > 0) {
      context += `Collaborators (${connections.collaborators.length}):\n`;
      connections.collaborators.slice(0, 10).forEach((c) => {
        context += `- ${c.name}\n`;
      });
      context += '\n';
    }
    if (connections.organizations.length > 0) {
      context += `Organizations (${connections.organizations.length}):\n`;
      connections.organizations.slice(0, 10).forEach((o) => {
        context += `- ${o.name}\n`;
      });
      context += '\n';
    }
    if (connections.members.length > 0) {
      context += `Members (${connections.members.length}):\n`;
      connections.members.slice(0, 10).forEach((m) => {
        context += `- ${m.name}${m.role ? ` (${m.role})` : ''}\n`;
      });
      context += '\n';
    }
  }

  return `${context}Question: ${question}\n\nAnswer:`;
};

export default api;
