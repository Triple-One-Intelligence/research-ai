import { useState } from 'react';
import './App.css';
import { LeftPanel } from './components/LeftPanel';

const App = () => {
  const [language, setLanguage] = useState<'nl' | 'en'>('nl');

  return (
    <div className="app-container">
      <header className="app-header">
        <h1>Research AI Assistant</h1>
        <div className="language-buttons">
          <button 
            className={`lang-btn ${language === 'nl' ? 'active' : ''}`}
            onClick={() => setLanguage('nl')}
          >
            NL
          </button>
          <button 
            className={`lang-btn ${language === 'en' ? 'active' : ''}`}
            onClick={() => setLanguage('en')}
          >
            EN
          </button>
        </div>
      </header>
      <main className="app-main">
        <LeftPanel />
        <div className="middle-panel">
          {/* Todo: Answer/Response panel */}
          <div className="placeholder-panel">
            <p>Middle column - Answer panel</p>
          </div>
        </div>
        <div className="right-panel">
          {/* Todo: Connections panel */}
          <div className="placeholder-panel">
            <p>Right column - Connections panel</p>
          </div>
        </div>
      </main>
    </div>
  );
};

export default App;
