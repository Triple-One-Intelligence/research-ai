import { useRef, useEffect } from 'react';
import './MiddlePanel.css';

interface MiddlePanelProps {
  text: string;
  isGenerating: boolean;
}

const MiddlePanel = ({ text, isGenerating }: MiddlePanelProps) => {
  const outputBoxRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (outputBoxRef.current && isGenerating) {
      outputBoxRef.current.scrollTop = outputBoxRef.current.scrollHeight;
    }
  }, [text, isGenerating]);

  return (
    <div className="middle-panel-container">
      <div className="middle-panel-header">
        <h2>AI Output</h2>
      </div>

      <div
        ref={outputBoxRef}
        className={`llm-output-box ${isGenerating ? 'generating' : ''}`}
      >
        {text || (
          <span style={{ color: '#888', fontStyle: 'italic' }}>
            Use the Ask button in the left panel to generate a response
          </span>
        )}
      </div>
    </div>
  );
};

export default MiddlePanel;
