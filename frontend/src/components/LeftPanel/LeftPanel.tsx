import { useState } from 'react';
import EntitySearchBar from './EntitySearchBar';
import type { EntitySuggestion } from '../../types';
import './LeftPanel.css';

interface LeftPanelProps {
  selectedEntity: EntitySuggestion | null;
  onEntitySelect: (entity: EntitySuggestion) => void;
  onEntityClear: () => void;
  onAsk: (prompt: string) => void;
  isGenerating: boolean;
}

const LeftPanel = ({ selectedEntity, onEntitySelect, onEntityClear, onAsk, isGenerating }: LeftPanelProps) => {
  const [customPrompt, setCustomPrompt] = useState('');

  const handleAsk = () => {
    if (!customPrompt.trim() || isGenerating) return;
    onAsk(customPrompt.trim());
    setCustomPrompt('');
  };

  const handleTemplate = (prompt: string) => {
    if (isGenerating) return;
    onAsk(prompt);
  };

  return (
    <aside className="left-panel">
      <EntitySearchBar
        onSelect={onEntitySelect}
        onClear={onEntityClear}
        selectedEntity={selectedEntity}
      />

      {selectedEntity && (
        <div className="prompt-buttons">
          <button
            className="prompt-btn"
            disabled={isGenerating}
            onClick={() => handleTemplate('Give an executive summary of this researcher and their work.')}
          >
            <span className="prompt-icon">📄</span>
            Executive Summary
          </button>
          <button
            className="prompt-btn"
            disabled={isGenerating}
            onClick={() => handleTemplate("What are the main strengths and gaps in this researcher's profile?")}
          >
            <span className="prompt-icon">💪</span>
            Strengths & Gaps
          </button>
        </div>
      )}

      <div className="custom-prompt-composer">
        <textarea
          className="prompt-textarea"
          placeholder="Write your question or instruction for the LLM…"
          value={customPrompt}
          onChange={(e) => setCustomPrompt(e.target.value)}
          rows={4}
          disabled={isGenerating}
        />
        <button
          className="ask-btn"
          onClick={handleAsk}
          disabled={!customPrompt.trim() || !selectedEntity || isGenerating}
        >
          {isGenerating ? 'Generating...' : 'Ask'}
        </button>
      </div>
    </aside>
  );
};

export default LeftPanel;
