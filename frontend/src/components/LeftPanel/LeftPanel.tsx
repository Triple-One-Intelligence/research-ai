import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import EntitySearchBar from './EntitySearchBar';
import type { EntitySuggestion } from '../../types';
import './LeftPanel.css';

// Props expected by LeftPanel:
//   onAsk – callback triggered when the user clicks the "Ask" button.
//   isGenerating – flag indicating whether the LLM is currently streaming a response.
interface LeftPanelProps {
  onAsk: (prompt: string) => void;
  isGenerating: boolean;
  selectedEntity: EntitySuggestion | null;
  onEntitySelect: (entity: EntitySuggestion) => void;
  onEntityClear: () => void;
  onRagTest: () => void;
}

// Main functional component. Destructures props for easy access.
const LeftPanel = ({ onAsk, isGenerating, selectedEntity, onEntitySelect, onEntityClear, onRagTest }: LeftPanelProps) => {
  const { t } = useTranslation();
  // State for the free‑form custom prompt the user can type.
  const [customPrompt, setCustomPrompt] = useState('');

  return (
    // The main container for the left panel.
    <aside className="left-panel">
      {/* Component for searching and selecting entities. */}
      <EntitySearchBar
        onSelect={onEntitySelect} // Callback for when an entity is selected.
        onClear={onEntityClear}   // Callback for when the selected entity is cleared.
        selectedEntity={selectedEntity} // The currently selected entity.
      />

      {/* Conditional rendering of prompt buttons based on whether an entity is selected. */}
      {selectedEntity && (
        <div className="prompt-buttons">
          {/* Button for generating an executive summary. */}
          <button 
            className="prompt-btn"
            onClick={() => onAsk(t('leftPanel.executiveSummaryPrompt'))}
          >
            <span className="prompt-icon">📄</span>
            {t('leftPanel.executiveSummary')}
          </button>
          {/* Button for generating strengths and gaps analysis. */}
          <button 
            className="prompt-btn"
            onClick={() => onAsk(t('leftPanel.strengthsGapsPrompt'))}
          >
            <span className="prompt-icon">💪</span>
            {t('leftPanel.strengthsGaps')}
          </button>

          {/* NEW: RAG-TEST button */}
          <button
            className="prompt-btn"
            onClick={onRagTest}
            disabled={isGenerating}
          >
              RAG-TEST
          </button>
        </div>
      )}

      {/* Section for composing a custom prompt. */}
      <div className="custom-prompt-composer">
        {/* Textarea for user to type their custom question/instruction. */}
        <textarea
          className="prompt-textarea"
          placeholder={t('leftPanel.promptPlaceholder')}
          value={customPrompt} // Binds the textarea value to the customPrompt state.
          onChange={(e) => setCustomPrompt(e.target.value)} // Updates state on input change.
          rows={4} // Sets the initial number of rows for the textarea.
        />
        {/* Button to trigger the LLM query. */}
        <button
          className="ask-btn"
          onClick={() => onAsk(customPrompt)} // Calls the onAsk prop function when clicked.
          disabled={isGenerating || !customPrompt.trim()} // Disables the button while a response is being generated.
        >
          {/* Changes button text based on generation status. */}
          {isGenerating ? t('leftPanel.askButtonGenerating') : t('leftPanel.askButton')}
        </button>
      </div>
    </aside>
  );
};

// Exports the LeftPanel component for use in other parts of the application.
export default LeftPanel;
