import { useState, useCallback, useRef, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import './App.css';
import { LeftPanel } from './components/LeftPanel';
import { MiddlePanel } from './components/MiddlePanel';
import { RightPanel } from './components/RightPanel';
import type { EntitySuggestion } from './types';
import { API_BASE } from './api';

// Shared SSE stream reader — works for both `/chat` and `/generate`.
//
// Assumptions:
// - The backend streams "SSE-like" lines in the form `data: <json>` (and `data: [DONE]` at the end).
// - Each parsed payload may contain either `token`, `debug`, or `error`.
const streamSSE = async (
  url: string,
  body: Record<string, unknown>,
  onChunk: (chunk: string) => void,
  onComplete: () => void,
  onDebug?: (info: Record<string, unknown>) => void,
  abortSignal?: AbortSignal,
) => {
  try {
    const resp = await fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
      signal: abortSignal,
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

      // SSE framing is line-based; we buffer partial lines across reads.
      buf += decoder.decode(value, { stream: true });
      const lines = buf.split('\n');
      buf = lines.pop() ?? '';
      for (const line of lines) {
        if (!line.startsWith('data: ')) continue;
        const payload = line.slice(6);
        if (payload === '[DONE]') break;
        try {
          const data = JSON.parse(payload);

          // `debug` is optional metadata; `error` stops the stream; `token` is appended to the UI.
          if (data.debug && onDebug) { onDebug(data.debug); continue; }
          if (data.error) { onChunk(`Error: ${data.error}`); break; }
          if (data.token) onChunk(data.token);
        } catch { /* skip malformed */ }
      }
    }
    onComplete();
  } catch (error) {
    // If we cancelled the request, let the UI settle without showing a noisy error.
    if (abortSignal?.aborted) {
      onComplete();
      return;
    }
    onChunk('Error: ' + (error instanceof Error ? error.message : 'Unknown error'));
    onComplete();
  }
};


const MIN_COL = 200;
const MAX_COL = 700;

// Pattern: Mediator — App centralizes state and communication between panels.
const App = () => {
  const [selectedEntity, setSelectedEntity] = useState<EntitySuggestion | null>(null);
  const [responseText, setResponseText] = useState<string>('');
  const [isGenerating, setIsGenerating] = useState<boolean>(false);
  const [debugInfo, setDebugInfo] = useState<Record<string, unknown> | null>(null);
  const abortControllerRef = useRef<AbortController | null>(null);

  const [leftWidth, setLeftWidth] = useState(380);
  const [rightWidth, setRightWidth] = useState(360);
  const dragging = useRef<{ side: 'left' | 'right'; startX: number; startWidth: number } | null>(null);

  const onMouseMove = useCallback((e: MouseEvent) => {
    if (!dragging.current) return;
    const delta = e.clientX - dragging.current.startX;
    const newWidth = Math.min(MAX_COL, Math.max(MIN_COL,
      dragging.current.side === 'left'
        ? dragging.current.startWidth + delta
        : dragging.current.startWidth - delta
    ));
    if (dragging.current.side === 'left') setLeftWidth(newWidth);
    else setRightWidth(newWidth);
  }, []);

  const onMouseUp = useCallback(() => {
    dragging.current = null;
    document.body.style.cursor = '';
    document.body.style.userSelect = '';
    window.removeEventListener('mousemove', onMouseMove);
    window.removeEventListener('mouseup', onMouseUp);
  }, [onMouseMove]);

  const startDrag = useCallback((side: 'left' | 'right', e: React.MouseEvent) => {
    e.preventDefault();
    dragging.current = {
      side,
      startX: e.clientX,
      startWidth: side === 'left' ? leftWidth : rightWidth,
    };
    document.body.style.cursor = 'col-resize';
    document.body.style.userSelect = 'none';
    window.addEventListener('mousemove', onMouseMove);
    window.addEventListener('mouseup', onMouseUp);
  }, [leftWidth, rightWidth, onMouseMove, onMouseUp]);

  const handleGenerate = (prompt: string) => {
    if (isGenerating) return;

    // Cancel any previous in-flight request.
    abortControllerRef.current?.abort();
    abortControllerRef.current = null;

    setResponseText('');
    setDebugInfo(null);
    setIsGenerating(true);

    const controller = new AbortController();
    abortControllerRef.current = controller;

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
        controller.signal,
      );
    } else {
      streamSSE(
        `${API_BASE}/chat`,
        { messages: [{ role: 'user', content: prompt }] },
        (chunk) => setResponseText((prev) => prev + chunk),
        () => setIsGenerating(false),
        undefined,
        controller.signal,
      );
    }
  };

  // When switching persons/entities, clear the AI output because it is tied to the previous entity.
  useEffect(() => {
    abortControllerRef.current?.abort();
    abortControllerRef.current = null;
    setResponseText('');
    setDebugInfo(null);
    setIsGenerating(false);
  }, [selectedEntity?.id, selectedEntity?.type]);
  const handleTop5Pubs = () => {
    if (isGenerating || !selectedEntity) return;
  
    setResponseText('');
    setDebugInfo(null);
    setIsGenerating(true);
  
    const langStr = language === 'nl' ? 'Dutch' : 'English';
  
    // send language as query param, body only contains selected_entity
    const url = `${API_BASE}/prompt_top5publications?language=${encodeURIComponent(langStr)}`;
  
    streamSSE(
      url,
      {
        id: String(selectedEntity.id),
        type: selectedEntity.type,
        label: selectedEntity.label,
      },
      (chunk) => setResponseText((prev) => prev + chunk),
      () => setIsGenerating(false),
      (info) => setDebugInfo(info),
    );
  };

  const { t, i18n } = useTranslation();
  const language = i18n.language as 'en' | 'nl';

  const changeLanguage = (lng: 'en' | 'nl') => {
    i18n.changeLanguage(lng);
  };

  const previewPR = import.meta.env.VITE_PREVIEW_PR;
  if (previewPR) document.title = `[PR #${previewPR}] Research AI`;

  return (
    <div className="app-container">
      {previewPR && (
        <div style={{ background: '#ff6b00', color: '#fff', textAlign: 'center', padding: '4px 0', fontSize: '13px', fontWeight: 600 }}>
          ⚠ PREVIEW — PR #{previewPR} — Dit is niet de productie-omgeving
        </div>
      )}
      <header className="app-header">
        <h1>{previewPR ? `[PR #${previewPR}] ${t('header.title')}` : t('header.title')}</h1>
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
      <main className="app-main" style={{ gridTemplateColumns: `${leftWidth}px 8px 1fr 8px ${rightWidth}px` }}>
        <LeftPanel
          selectedEntity={selectedEntity}
          onAsk={handleGenerate}
          onTop5Pubs={handleTop5Pubs}
          isGenerating={isGenerating}
          onEntitySelect={setSelectedEntity}
          onEntityClear={() => setSelectedEntity(null)}
        />
        <div className="resize-handle" onMouseDown={(e) => startDrag('left', e)} />
        <div className="middle-panel">
          {debugInfo && (
            <details className="rag-debug">
              <summary>
                RAG Debug &middot; {(debugInfo.publications_found as number) ?? 0} pubs &middot; {(debugInfo.model as string) ?? '?'}
              </summary>
              <div className="rag-debug-sections">
                <details>
                  <summary>User prompt</summary>
                  <pre>{debugInfo.user_prompt as string}</pre>
                </details>

                <details>
                  <summary>Entity</summary>
                  <pre>{JSON.stringify(debugInfo.entity, null, 2)}</pre>
                </details>

                <details>
                  <summary>System prompt</summary>
                  <pre className="rag-debug-scroll">{debugInfo.system_prompt as string}</pre>
                </details>

                <details>
                  <summary>Publications ({(debugInfo.publications_found as number) ?? 0})</summary>
                  <div className="rag-debug-scroll">
                    {((debugInfo.publications as Array<Record<string, unknown>>) ?? []).map((pub, i) => (
                      <details key={i} className="rag-debug-pub">
                        <summary>
                          {pub.title as string ?? 'Untitled'} ({pub.year as string ?? '?'})
                        </summary>
                        <pre>{JSON.stringify(pub, null, 2)}</pre>
                      </details>
                    ))}
                  </div>
                </details>

                <details>
                  <summary>Full messages (sent to LLM)</summary>
                  <pre className="rag-debug-scroll">{JSON.stringify(debugInfo.full_messages, null, 2)}</pre>
                </details>
              </div>
            </details>
          )}
          <MiddlePanel text={responseText} isGenerating={isGenerating} />
        </div>
        <div className="resize-handle" onMouseDown={(e) => startDrag('right', e)} />
        <RightPanel selectedEntity={selectedEntity} onEntitySelect={setSelectedEntity} />
      </main>
    </div>
  );
};

export default App;
