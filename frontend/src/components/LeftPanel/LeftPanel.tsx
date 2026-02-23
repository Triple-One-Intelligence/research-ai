import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import EntitySearchBar from './EntitySearchBar';
import type { EntitySuggestion } from '../../types';
import './LeftPanel.css';

const LeftPanel = () => {
  const { t } = useTranslation();
  const [selectedEntity, setSelectedEntity] = useState<EntitySuggestion | null>(null);
  const [customPrompt, setCustomPrompt] = useState('');

  const handleEntitySelect = (entity: EntitySuggestion) => {
    setSelectedEntity(entity);
  };

  const handleEntityClear = () => {
    setSelectedEntity(null);
  };

  return (
    <aside className="left-panel">
      <EntitySearchBar 
        onSelect={handleEntitySelect}
        onClear={handleEntityClear}
        selectedEntity={selectedEntity}
      />
      
      {selectedEntity && (
        <div className="prompt-buttons">
          <button className="prompt-btn">
            <span className="prompt-icon">📄</span>
            {t('leftPanel.executiveSummary')}
          </button>
          <button className="prompt-btn">
            <span className="prompt-icon">💪</span>
            {t('leftPanel.strengthsGaps')}
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
        <button className="ask-btn">
          {t('leftPanel.askButton')}
        </button>
      </div>
    </aside>
  );
};

export default LeftPanel;
