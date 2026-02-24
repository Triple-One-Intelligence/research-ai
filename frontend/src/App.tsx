import { useState } from 'react';
import './App.css';
import { LeftPanel } from './components/LeftPanel';
import { RightPanel } from './components/RightPanel';
import type { EntitySuggestion } from './types';

const App = () => {
  const [selectedEntity, setSelectedEntity] = useState<EntitySuggestion | null>(null);

  return (
    <div className="app-container">
      <header className="app-header">
        <h1>Research AI Assistant</h1>
      </header>
      <main className="app-main">
        <LeftPanel
          selectedEntity={selectedEntity}
          onEntitySelect={setSelectedEntity}
          onEntityClear={() => setSelectedEntity(null)}
        />
        <div className="middle-panel">
          {/* Todo: Answer/Response panel */}
          <div className="placeholder-panel">
            <p>Middle column - Answer panel</p>
          </div>
        </div>
        <RightPanel selectedEntity={selectedEntity} />
      </main>
    </div>
  );
};

export default App;
