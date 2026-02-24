import { useState } from 'react';
import EntitySearchBar from './EntitySearchBar';
import type { EntitySuggestion } from '../../types';
import './LeftPanel.css';

interface LeftPanelProps {
  selectedEntity: EntitySuggestion | null;
  onEntitySelect: (entity: EntitySuggestion) => void;
  onEntityClear: () => void;
}

const LeftPanel = ({ selectedEntity, onEntitySelect, onEntityClear }: LeftPanelProps) => {
  const [customPrompt, setCustomPrompt] = useState('');

  return (
    <aside className="left-panel">
      <EntitySearchBar
        onSelect={onEntitySelect}
        onClear={onEntityClear}
        selectedEntity={selectedEntity}
      />

      {selectedEntity && (
        <div className="prompt-buttons">
          <button className="prompt-btn">
            <span className="prompt-icon">📄</span>
            Executive Summary
          </button>
          <button className="prompt-btn">
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
        />
        <button className="ask-btn">
          Ask
        </button>
      </div>
    </aside>
  );
};

export default LeftPanel;
