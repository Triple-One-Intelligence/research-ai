import React, { useRef, useEffect } from 'react';
import ReactMarkdown from 'react-markdown';
import './MiddlePanel.css';
import { useTranslation } from 'react-i18next';

interface MiddlePanelProps {
  text: string;
  isGenerating: boolean;
}

/**
 * Turn DOI strings into clickable links and numbered citations [N] into
 * anchors that scroll to the corresponding DOI in the debug panel.
 */
function linkifyDois(text: string): string {
  // Turn bare DOI references like "10.xxxx/yyyy" into markdown links
  return text.replace(
    /\b(10\.\d{4,}\/[^\s,)}\]]+)/g,
    '[$1](https://doi.org/$1)',
  );
}

export const MiddlePanel: React.FC<MiddlePanelProps> = ({ text, isGenerating }) => {
  const outputBoxRef = useRef<HTMLDivElement>(null);
  const { t } = useTranslation();

  useEffect(() => {
    if (outputBoxRef.current && isGenerating) {
      outputBoxRef.current.scrollTop = outputBoxRef.current.scrollHeight;
    }
  }, [text, isGenerating]);

  const processedText = text ? linkifyDois(text) : '';

  return (
    <div className="middle-panel-container">
      <div className="middle-panel-header">
        <h2>{t('middlePanel.header')}</h2>
      </div>

      <div
        ref={outputBoxRef}
        className={`llm-output-box ${isGenerating ? 'generating' : ''}`}
      >
        {processedText ? (
          <ReactMarkdown>{processedText}</ReactMarkdown>
        ) : (
          isGenerating ? null : (
            <span style={{ color: '#888', fontStyle: 'italic' }}>
              {t('middlePanel.outputPlaceholder')}
            </span>
          )
        )}
      </div>
    </div>
  );
};
