import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import EntitySearchBar from './EntitySearchBar';
import type { EntitySuggestion } from '../../types';
import './LeftPanel.css';

interface LeftPanelProps {
  onAsk: (prompt: string) => void;
  isGenerating: boolean;
  selectedEntity: EntitySuggestion | null;
  onEntitySelect: (entity: EntitySuggestion) => void;
  onEntityClear: () => void;
}

const LeftPanel = ({ onAsk, isGenerating, selectedEntity, onEntitySelect, onEntityClear }: LeftPanelProps) => {
  const { t } = useTranslation();
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
          <button
            className="prompt-btn"
            onClick={() => setCustomPrompt(t('leftPanel.topOrganizationsPrompt', { entity: selectedEntity.label }))}
          >
            <span className="prompt-icon">🏢</span>
            {t('leftPanel.topOrganizations')}
          </button>
          <button
            className="prompt-btn"
            onClick={() => setCustomPrompt(t('leftPanel.publicationsPrompt', { entity: selectedEntity.label }))}
          >
            <span className="prompt-icon">📚</span>
            {t('leftPanel.relevantPublications')}
          </button>
          <button
            className="prompt-btn"
            onClick={() => setCustomPrompt(t('leftPanel.uvCVPrompt', { entity: selectedEntity.label }))}
          >
            <span className="prompt-icon">🎓</span>
            {t('leftPanel.uvProfileCV')}
          </button>
        </div>
      )}

      <div className="custom-prompt-composer">
        <textarea
          className="prompt-textarea"
          placeholder={t('leftPanel.promptPlaceholder')}
          value={customPrompt}
          onChange={(e) => setCustomPrompt(e.target.value)}
          rows={4}
        />
        <button
          className="ask-btn"
          onClick={() => onAsk(customPrompt)}
          disabled={isGenerating || !customPrompt.trim()}
        >
          {isGenerating ? t('leftPanel.askButtonGenerating') : t('leftPanel.askButton')}
        </button>
      </div>
    </aside>
  );
};

export default LeftPanel;
