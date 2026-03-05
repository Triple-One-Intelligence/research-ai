import axios, { AxiosError } from 'axios';
import type { ChatMessage, ChatResponse } from '../types';

const AIapi = axios.create({
  baseURL: import.meta.env.VITE_API_URL || "/api"  
});

export const promptTheAI = async (messages: ChatMessage[]): Promise<string> => {
  
  const baseText = '[..TEST..]'
  try{

    const fullResponse = await axios.post<ChatResponse>('/api/chat', { messages });
    const assistantText = fullResponse.data.choices?.[0]?.message?.content ?? '';
    return assistantText

  } catch (e) {

    const err = e as AxiosError
    if (err.response) {
      // server returned non-2xx
      console.error('AI server error', err.response.status, err.response.data);
      return 'AI server error: ' + err.response.status + "  " + err.message
    } 
    else {
      // network / CORS / other
      console.error('Request failed (ai)', err.message);
      return 'Request failed (ai): '+ err.message
    }
    return baseText
  }

}

export default AIapi;