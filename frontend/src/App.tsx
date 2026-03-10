import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import './App.css';
import { LeftPanel } from './components/LeftPanel';
import { MiddlePanel } from './components/MiddlePanel';
import { RightPanel } from './components/RightPanel';
import type { EntitySuggestion } from './types';
import { askWithRag, fetchRagDocs } from './api';

// Ask response generation function. Takes a prompt and two callbacks:
// one for handling incoming chunks of text, and one for when the response is complete.


// Main App component – orchestrates state and renders the three‑panel layout.
const App = () => {
  const [selectedEntity, setSelectedEntity] = useState<EntitySuggestion | null>(null);
  const [responseText, setResponseText] = useState<string>('');
  const [isGenerating, setIsGenerating] = useState<boolean>(false);


  const handleGenerate = async (prompt: string) => {
    if (isGenerating) return;
    if (!selectedEntity) {
      // You can decide whether to block or fall back to plain /chat here.
      setResponseText('Please select an entity first.');
      return;
    }
    setResponseText('');
    setIsGenerating(true);
    try {
      const res = await askWithRag(prompt, selectedEntity);
      setResponseText(res.answer);
      // Optionally: store res.sources in state and render them somewhere.
    } catch (error) {
      const message =
        error instanceof Error ? error.message : 'Unknown error';
      setResponseText('Error: ' + message);
    } finally {
      setIsGenerating(false);
    }
  };

  const handleRagTest = async () => {
    if (!selectedEntity) {
      setResponseText('Please select an entity first.');
      return;
    }
    setResponseText('');
    setIsGenerating(true);
    try {
      const res = await fetchRagDocs(t('leftPanel.executiveSummaryPrompt'), selectedEntity);
      setResponseText(res.context_text);
      
    } catch (error) {
      const message =
        error instanceof Error ? error.message : 'Unknown error';
      setResponseText('Error (RAG-TEST): ' + message);
    } finally {
      setIsGenerating(false);
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
          onRagTest={handleRagTest}
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
