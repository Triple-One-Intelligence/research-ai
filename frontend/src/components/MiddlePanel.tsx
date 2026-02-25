import React, { useRef, useEffect } from 'react';
import './MiddlePanel.css';

// Props definition for the MiddlePanel component.
// - text: The AI generated response text to display.
// - isGenerating: Flag indicating whether the AI is currently streaming a response.
interface MiddlePanelProps {
  text: string;
  isGenerating: boolean;
}

// The MiddlePanel functional component renders the AI output area.
// It automatically scrolls to the bottom when new text arrives while generation is in progress.
export const MiddlePanel: React.FC<MiddlePanelProps> = ({ text, isGenerating }) => {
  // Ref to the output container div so we can manipulate its scroll position.
  const outputBoxRef = useRef<HTMLDivElement>(null);

  // Effect runs whenever `text` or `isGenerating` changes.
  // If we are still generating, scroll the container to the bottom to keep the newest text visible.
  useEffect(() => {
    if (outputBoxRef.current && isGenerating) {
      outputBoxRef.current.scrollTop = outputBoxRef.current.scrollHeight;
    }
  }, [text, isGenerating]);

  return (
    <div className="middle-panel-container">
      {/* Header for the panel */}
      <div className="middle-panel-header">
        <h2>AI Output</h2>
      </div>

      {/* Main output box. The `generating` class adds a blinking cursor when streaming. */}
      <div
        ref={outputBoxRef}
        className={`llm-output-box ${isGenerating ? 'generating' : ''}`}
      >
        {/* Show the AI text if available; otherwise display a helpful placeholder. */}
        {text || (
          <span style={{ color: '#888', fontStyle: 'italic' }}>
            Use the Ask button in the left panel to generate a response
          </span>
        )}
      </div>
    </div>
  );
};
