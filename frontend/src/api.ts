
import axios from 'axios';
import type { EntitySuggestion } from './types';

const api = axios.create({
  baseURL: import.meta.env.VITE_API_URL || "http://localhost:8000"
});

export const searchEntities = async (
  query: string,
  _types: string[] = ['person', 'organization'],
  _limit: number = 10
): Promise<EntitySuggestion[]> => {
  // Todo: Implement actual API call
  return getMockSuggestions(query);
};

function getUsers(): Promise<EntitySuggestion[]> {
  // For now, consider the data is stored on a static `users.json` file
  return fetch('/autocomplete')
    // the JSON body is taken from the response
    .then(res => res.json())
    .then(res => {
      // The response has an `any` type, so we need to cast
      // it to the `User` type, and return it from the promise
      return res as EntitySuggestion[]
    })
}

const getMockSuggestions = (query: string): EntitySuggestion[] => {

  // const mockData: EntitySuggestion[] = [
  //   { id: 'pure:org:1', type: 'organization', label: 'Faculty of Science', extra: 'Utrecht University' },
  //   { id: 'pure:org:2', type: 'organization', label: 'Department of Computer Science', extra: 'Faculty of Science' },
  //   { id: 'pure:org:3', type: 'organization', label: 'Chair of Petrology', extra: 'Faculty of Geosciences' },
  //   { id: 'pure:person:1', type: 'person', label: 'Dr. Jan de Vries', extra: 'Computer Science' },
  //   { id: 'pure:person:2', type: 'person', label: 'Prof. Maria van den Berg', extra: 'Faculty of Science' },
  //   { id: 'pure:person:3', type: 'person', label: 'Dr. Peter Jansen', extra: 'Petrology' },
  //];

  const lowerQuery = query.toLowerCase();
  return mockData.filter(
    item => 
      item.label.toLowerCase().includes(lowerQuery) ||
      item.extra?.toLowerCase().includes(lowerQuery)
  );
};

export default api;
