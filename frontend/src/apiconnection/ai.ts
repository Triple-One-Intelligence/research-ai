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

export const promptTheAIStream = async (
  messages: ChatMessage[],
  onChunk: (chunk: string) => void,
  onComplete: () => void,
): Promise<void> => {
  try {
    const res = await fetch('/api/chat-stream', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ messages }),
    });

    if (!res.ok) {
      // Similar to `err.response` branch
      console.error('AI server error (stream)', res.status, await res.text());
      onChunk('AI server error (stream): ' + res.status);
      onComplete();
      return;
    }

    if (!res.body) {
      onComplete();
      return;
    }

    const reader = res.body.getReader();
    const decoder = new TextDecoder('utf-8');

    let done = false;
    while (!done) {
      const result = await reader.read();
      done = result.done ?? false;

      if (done) {
        onComplete();
        return;
      }

      if (result.value) {
        const text = decoder.decode(result.value, { stream: !done });
        // For SSE, split on "\n\n" and strip "data: "
        for (const event of text.split('\n\n')) {
          const line = event.trim();
          if (!line.startsWith('data:')) continue;
          const payload = line.slice(5).trim();
          // If Ollama sends JSON per line, parse and extract .message.content delta as neede
          onChunk(payload);
        }
      }
    }
  } catch (e) {
    // Similar to the "network / CORS / other" branch
    const err = e as Error;
    console.error('Request failed (ai stream)', err.message);
    onChunk('Request failed (ai stream): ' + err.message);
    onComplete();
  }
};

export default AIapi;