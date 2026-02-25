import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import EntitySearchBar from './EntitySearchBar';
import type { EntitySuggestion } from '../../types';
import './LeftPanel.css';

// Props expected by LeftPanel:
//   onAsk – callback triggered when the user clicks the "Ask" button.
//   isGenerating – flag indicating whether the LLM is currently streaming a response.
interface LeftPanelProps {
  onAsk: () => void;
  isGenerating: boolean;
  selectedEntity: EntitySuggestion | null;
  onEntitySelect: (entity: EntitySuggestion) => void;
  onEntityClear: () => void;
}

// Main functional component. Destructures props for easy access.
const LeftPanel = ({ onAsk, isGenerating, selectedEntity, onEntitySelect, onEntityClear }: LeftPanelProps) => {
  const { t } = useTranslation();
    // State to keep track of the currently selected entity from the search bar.
  const [selectedEntity, setSelectedEntity] = useState<EntitySuggestion | null>(null);
  // State for the free‑form custom prompt the user can type.
  const [customPrompt, setCustomPrompt] = useState('');

    // Called by EntitySearchBar when the user picks an entity.
  const handleEntitySelect = (entity: EntitySuggestion) => {
    setSelectedEntity(entity);
  };

    // Clears the currently selected entity – used by the clear button in EntitySearchBar.
  const handleEntityClear = () => {
    setSelectedEntity(null);
  };

  return (
    // The main container for the left panel.
    <aside className="left-panel">
      {/* Component for searching and selecting entities. */}
      <EntitySearchBar
        onSelect={handleEntitySelect} // Callback for when an entity is selected.
        onClear={handleEntityClear}   // Callback for when the selected entity is cleared.
        selectedEntity={selectedEntity} // The currently selected entity.
      />

      {/* Conditional rendering of prompt buttons based on whether an entity is selected. */}
      {selectedEntity && (
        <div className="prompt-buttons">
          {/* Button for generating an executive summary. */}
          <button className="prompt-btn">
            <span className="prompt-icon">📄</span>
            {t('leftPanel.executiveSummary')}
          </button>
          {/* Button for generating strengths and gaps analysis. */}
          <button className="prompt-btn">
            <span className="prompt-icon">💪</span>
            {t('leftPanel.strengthsGaps')}
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
          onClick={onAsk} // Calls the onAsk prop function when clicked.
          disabled={isGenerating} // Disables the button while a response is being generated.
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
