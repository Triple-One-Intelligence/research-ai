import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import './App.css';
import { LeftPanel } from './components/LeftPanel';
import { MiddlePanel } from './components/MiddlePanel';
import { RightPanel } from './components/RightPanel';
import type { EntitySuggestion } from './types';
const API_BASE = import.meta.env.VITE_API_URL || '/api';

// Shared SSE stream reader — works for both /chat and /generate
const streamSSE = async (
  url: string,
  body: Record<string, unknown>,
  onChunk: (chunk: string) => void,
  onComplete: () => void,
) => {
  try {
    const resp = await fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    });

    if (!resp.ok || !resp.body) {
      onChunk(`Error: ${resp.status} ${resp.statusText}`);
      onComplete();
      return;
    }

    const reader = resp.body.getReader();
    const decoder = new TextDecoder();
    let buf = '';

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buf += decoder.decode(value, { stream: true });
      const lines = buf.split('\n');
      buf = lines.pop() ?? '';
      for (const line of lines) {
        if (!line.startsWith('data: ')) continue;
        const payload = line.slice(6);
        if (payload === '[DONE]') break;
        try {
          const data = JSON.parse(payload);
          if (data.error) { onChunk(`Error: ${data.error}`); break; }
          if (data.token) onChunk(data.token);
        } catch { /* skip malformed */ }
      }
    }
    onComplete();
  } catch (error) {
    onChunk('Error: ' + (error instanceof Error ? error.message : 'Unknown error'));
    onComplete();
  }
};


// Main App component – orchestrates state and renders the three‑panel layout.
const App = () => {
  const [selectedEntity, setSelectedEntity] = useState<EntitySuggestion | null>(null);
  const [responseText, setResponseText] = useState<string>('');
  const [isGenerating, setIsGenerating] = useState<boolean>(false);

  const handleGenerate = (prompt: string) => {
    if (isGenerating) return;

    setResponseText('');
    setIsGenerating(true);

    if (selectedEntity) {
      // RAG-augmented streaming: include entity context + vector retrieval
      streamSSE(
        `${API_BASE}/generate`,
        {
          prompt,
          entity: {
            id: selectedEntity.id,
            type: selectedEntity.type,
            label: selectedEntity.label,
          },
        },
        (chunk) => setResponseText((prev) => prev + chunk),
        () => setIsGenerating(false),
      );
    } else {
      // Plain streaming chat (no RAG context)
      streamSSE(
        `${API_BASE}/chat`,
        { messages: [{ role: 'user', content: prompt }] },
        (chunk) => setResponseText((prev) => prev + chunk),
        () => setIsGenerating(false),
      );
    }
  };

  const { t, i18n } = useTranslation();
  const language = i18n.language as 'en' | 'nl';

  const changeLanguage = (lng: 'en' | 'nl') => {
    i18n.changeLanguage(lng);
  };

  return (
    <div className="app-container">
      <header className="app-header">
        <h1>{t('header.title')}</h1>
        <div className="language-buttons">
          <button
            className={`lang-btn ${language === 'nl' ? 'active' : ''}`}
            onClick={() => changeLanguage('nl')}
          >
            NL
          </button>
          <button
            className={`lang-btn ${language === 'en' ? 'active' : ''}`}
            onClick={() => changeLanguage('en')}
          >
            EN
          </button>
        </div>
      </header>
      <main className="app-main">
        <LeftPanel
          selectedEntity={selectedEntity}
          onAsk={handleGenerate}
          isGenerating={isGenerating}
          onEntitySelect={setSelectedEntity}
          onEntityClear={() => setSelectedEntity(null)}
        />
        <div className="middle-panel">
          <MiddlePanel text={responseText} isGenerating={isGenerating} />
        </div>
        <RightPanel selectedEntity={selectedEntity} />
      </main>
    </div>
  );
};

export default App;
