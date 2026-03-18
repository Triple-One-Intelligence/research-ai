import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import * as enPrompts from '../../prompts/en';
import * as nlPrompts from '../../prompts/nl';
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
  const { t, i18n } = useTranslation();
  const [customPrompt, setCustomPrompt] = useState('');

  const getLocalizedPrompt = (type: 'executiveSummary' | 'strengthsGaps' | 'topOrganizations' | 'publications' | 'uvCV') => {
    const promptModule = i18n.language === 'nl' ? nlPrompts : enPrompts;
    return promptModule.getPrompt(type, selectedEntity?.label || '');
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
            onClick={() => onAsk(getLocalizedPrompt('executiveSummary'))}
            disabled={isGenerating}
          >
            <span className="prompt-icon">📄</span>
            {t('leftPanel.executiveSummary')}
          </button>
          <button
            className="prompt-btn"
            onClick={() => onAsk(getLocalizedPrompt('strengthsGaps'))}
            disabled={isGenerating}
          >
            <span className="prompt-icon">⚖️</span>
            {t('leftPanel.strengthsGaps')}
          </button>
          <button
            className="prompt-btn"
            onClick={() => onAsk(getLocalizedPrompt('topOrganizations'))}
            disabled={isGenerating}
          >
            <span className="prompt-icon">🏢</span>
            {t('leftPanel.topOrganizations')}
          </button>
          <button
            className="prompt-btn"
            onClick={() => onAsk(getLocalizedPrompt('publications'))}
            disabled={isGenerating}
          >
            <span className="prompt-icon">📚</span>
            {t('leftPanel.relevantPublications')}
          </button>
          <button
            className="prompt-btn"
            onClick={() => onAsk(getLocalizedPrompt('uvCV'))}
            disabled={isGenerating}
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
