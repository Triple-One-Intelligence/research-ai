import React, { useRef, useEffect } from 'react';
import ReactMarkdown from 'react-markdown';
import './MiddlePanel.css';
import { useTranslation } from 'react-i18next';

interface MiddlePanelProps {
  text: string;
  isGenerating: boolean;
}

export const MiddlePanel: React.FC<MiddlePanelProps> = ({ text, isGenerating }) => {
  const outputBoxRef = useRef<HTMLDivElement>(null);
  const { t } = useTranslation();

  useEffect(() => {
    if (outputBoxRef.current && isGenerating) {
      outputBoxRef.current.scrollTop = outputBoxRef.current.scrollHeight;
    }
  }, [text, isGenerating]);

  return (
    <div className="middle-panel-container">
      <div className="middle-panel-header">
        <h2>{t('middlePanel.header')}</h2>
      </div>

      <div
        ref={outputBoxRef}
        className={`llm-output-box ${isGenerating ? 'generating' : ''}`}
      >
        {text ? (
          <ReactMarkdown
            components={{
              a: ({ href, children, ...props }) => (
                <a
                  href={href?.startsWith('https://') ? href : undefined}
                  target="_blank"
                  rel="noopener noreferrer"
                  {...props}
                >
                  {children}
                </a>
              ),
            }}
          >{text}</ReactMarkdown>
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
