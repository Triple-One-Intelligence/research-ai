import { useState, useEffect, useCallback } from 'react';
import './App.css';
import { LeftPanel } from './components/LeftPanel';
import { MiddlePanel } from './components/MiddlePanel';
import { RightPanel } from './components/RightPanel';
import { fetchConnections, sendChat, buildContextPrompt } from './api';
import type { EntitySuggestion, ConnectionsResponse } from './types';

const App = () => {
  const [selectedEntity, setSelectedEntity] = useState<EntitySuggestion | null>(null);
  const [connections, setConnections] = useState<ConnectionsResponse | null>(null);
  const [connectionsLoading, setConnectionsLoading] = useState(false);
  const [connectionsError, setConnectionsError] = useState<string | null>(null);
  const [responseText, setResponseText] = useState('');
  const [isGenerating, setIsGenerating] = useState(false);

  useEffect(() => {
    if (!selectedEntity) {
      setConnections(null);
      setConnectionsError(null);
      setResponseText('');
      return;
    }

    let cancelled = false;
    setConnectionsLoading(true);
    setConnectionsError(null);

    fetchConnections(selectedEntity)
      .then((data) => {
        if (!cancelled) setConnections(data);
      })
      .catch((err) => {
        if (!cancelled) setConnectionsError(err.message ?? 'Failed to load connections');
      })
      .finally(() => {
        if (!cancelled) setConnectionsLoading(false);
      });

    return () => { cancelled = true; };
  }, [selectedEntity]);

  const handleAsk = useCallback(async (question: string) => {
    if (!selectedEntity || !question.trim() || isGenerating) return;

    setResponseText('');
    setIsGenerating(true);

    try {
      const prompt = buildContextPrompt(selectedEntity, connections, question);
      const text = await sendChat(prompt);
      setResponseText(text);
    } catch {
      setResponseText('Failed to get a response. Please try again.');
    } finally {
      setIsGenerating(false);
    }
  }, [selectedEntity, connections, isGenerating]);

  return (
    <div className="app-container">
      <header className="app-header">
        <h1>Research AI Assistant</h1>
      </header>
      <main className="app-main">
        <LeftPanel
          selectedEntity={selectedEntity}
          onEntitySelect={setSelectedEntity}
          onEntityClear={() => setSelectedEntity(null)}
          onAsk={handleAsk}
          isGenerating={isGenerating}
        />
        <div className="middle-panel">
          <MiddlePanel text={responseText} isGenerating={isGenerating} />
        </div>
        <RightPanel
          connections={connections}
          loading={connectionsLoading}
          error={connectionsError}
          hasEntity={!!selectedEntity}
        />
      </main>
    </div>
  );
};

export default App;
