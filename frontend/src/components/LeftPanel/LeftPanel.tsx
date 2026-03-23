import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import * as enPrompts from '../../prompts/en';
import * as nlPrompts from '../../prompts/nl';
import EntitySearchBar from './EntitySearchBar';
import type { EntitySuggestion } from '../../types';
import './LeftPanel.css';

interface LeftPanelProps {
  onAsk: (prompt: string) => void;
  onAskPipeline: (promptType: string, prompt: string) => void;
  isGenerating: boolean;
  selectedEntity: EntitySuggestion | null;
  onEntitySelect: (entity: EntitySuggestion) => void;
  onEntityClear: () => void;
}

// Left column: lets the user pick an entity and compose a custom prompt.
// It also provides one-click prompt templates based on the selected entity.
const LeftPanel = ({ onAsk, onAskPipeline, isGenerating, selectedEntity, onEntitySelect, onEntityClear }: LeftPanelProps) => {
  const { t, i18n } = useTranslation();
  const [customPrompt, setCustomPrompt] = useState('');

  const getLocalizedPrompt = (type: 'executiveSummary' | 'topOrganizations' | 'topCollaborators' | 'recentPublications') => {
    const promptModule = i18n.language === 'nl' ? nlPrompts : enPrompts;
    return promptModule.getPrompt(type, selectedEntity?.label || '');
  };
  // The prompt text is entity-specific; when switching persons/entities it must be reset.
  useEffect(() => {
    setCustomPrompt('');
  }, [selectedEntity?.id, selectedEntity?.type]);

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
            onClick={() => onAskPipeline('executiveSummary', getLocalizedPrompt('executiveSummary'))}
            disabled={isGenerating}
          >
            <span className="prompt-icon">📄</span>
            {t('leftPanel.executiveSummary')}
          </button>
          <button
            className="prompt-btn"
            onClick={() => onAskPipeline('topOrganizations', getLocalizedPrompt('topOrganizations'))}
            disabled={isGenerating}
          >
            <span className="prompt-icon">🏢</span>
            {t('leftPanel.topOrganizations')}
          </button>
          <button
            className="prompt-btn"
            onClick={() => onAskPipeline('topCollaborators', getLocalizedPrompt('topCollaborators'))}
            disabled={isGenerating}
          >
            <span className="prompt-icon">🤝</span>
            {t('leftPanel.topCollaborators')}
          </button>
          <button
            className="prompt-btn"
            onClick={() => onAskPipeline('recentPublications', getLocalizedPrompt('recentPublications'))}
            disabled={isGenerating}
          >
            <span className="prompt-icon">📚</span>
            {t('leftPanel.recentPublications')}
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
