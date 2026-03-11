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
  onDebug?: (info: Record<string, unknown>) => void,
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
          if (data.debug && onDebug) { onDebug(data.debug); continue; }
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


// Main App component – orchestrates state and renders the three-panel layout.
const App = () => {
  const [selectedEntity, setSelectedEntity] = useState<EntitySuggestion | null>(null);
  const [responseText, setResponseText] = useState<string>('');
  const [isGenerating, setIsGenerating] = useState<boolean>(false);
  const [debugInfo, setDebugInfo] = useState<Record<string, unknown> | null>(null);

  const handleGenerate = (prompt: string) => {
    if (isGenerating) return;

    setResponseText('');
    setDebugInfo(null);
    setIsGenerating(true);

    if (selectedEntity) {
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
        (info) => setDebugInfo(info),
      );
    } else {
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
          {debugInfo && (
            <details className="rag-debug" style={{
              marginBottom: '1rem',
              padding: '0.75rem',
              background: '#1a1a2e',
              border: '1px solid #444',
              borderRadius: '6px',
              fontSize: '0.8rem',
              color: '#ccc',
            }}>
              <summary style={{ cursor: 'pointer', fontWeight: 'bold', color: '#7eb8da' }}>
                RAG Debug &middot; {(debugInfo.publications_found as number) ?? 0} pubs &middot; {(debugInfo.model as string) ?? '?'}
              </summary>
              <div style={{ marginTop: '0.5rem', display: 'flex', flexDirection: 'column', gap: '0.4rem' }}>

                <details>
                  <summary style={{ cursor: 'pointer', color: '#a8d8a8' }}>User prompt</summary>
                  <pre style={{ margin: '0.3rem 0 0 1rem', whiteSpace: 'pre-wrap', wordBreak: 'break-word' }}>
                    {debugInfo.user_prompt as string}
                  </pre>
                </details>

                <details>
                  <summary style={{ cursor: 'pointer', color: '#a8d8a8' }}>Entity</summary>
                  <pre style={{ margin: '0.3rem 0 0 1rem', whiteSpace: 'pre-wrap', wordBreak: 'break-word' }}>
                    {JSON.stringify(debugInfo.entity, null, 2)}
                  </pre>
                </details>

                <details>
                  <summary style={{ cursor: 'pointer', color: '#a8d8a8' }}>System prompt</summary>
                  <pre style={{ margin: '0.3rem 0 0 1rem', whiteSpace: 'pre-wrap', wordBreak: 'break-word', maxHeight: '300px', overflow: 'auto' }}>
                    {debugInfo.system_prompt as string}
                  </pre>
                </details>

                <details>
                  <summary style={{ cursor: 'pointer', color: '#a8d8a8' }}>
                    Publications ({(debugInfo.publications_found as number) ?? 0})
                  </summary>
                  <div style={{ margin: '0.3rem 0 0 1rem', maxHeight: '300px', overflow: 'auto' }}>
                    {((debugInfo.publications as Array<Record<string, unknown>>) ?? []).map((pub, i) => (
                      <details key={i} style={{ marginBottom: '0.3rem' }}>
                        <summary style={{ cursor: 'pointer', color: '#d4c89a' }}>
                          {pub.title as string ?? 'Untitled'} ({pub.year as string ?? '?'})
                        </summary>
                        <pre style={{ margin: '0.2rem 0 0 1rem', whiteSpace: 'pre-wrap', wordBreak: 'break-word', fontSize: '0.75rem' }}>
                          {JSON.stringify(pub, null, 2)}
                        </pre>
                      </details>
                    ))}
                  </div>
                </details>

                <details>
                  <summary style={{ cursor: 'pointer', color: '#a8d8a8' }}>Full messages (sent to LLM)</summary>
                  <pre style={{ margin: '0.3rem 0 0 1rem', whiteSpace: 'pre-wrap', wordBreak: 'break-word', maxHeight: '300px', overflow: 'auto' }}>
                    {JSON.stringify(debugInfo.full_messages, null, 2)}
                  </pre>
                </details>

              </div>
            </details>
          )}
          <MiddlePanel text={responseText} isGenerating={isGenerating} />
        </div>
        <RightPanel selectedEntity={selectedEntity} />
      </main>
    </div>
  );
};

export default App;
