import { useTranslation } from 'react-i18next';
import './App.css';
import { LeftPanel } from './components/LeftPanel';

const App = () => {
  const { t, i18n } = useTranslation();
  const language = i18n.language as 'en' | 'nl';

  const changeLanguage = (lng: 'en' | 'nl') => {
    i18n.changeLanguage(lng);
  };

  return (
    <div className="app-container">
      <header className="app-header">
        <h1>{t('header.title')}</h1>
        <div className="language-buttons">
          <button 
            className={`lang-btn ${language === 'nl' ? 'active' : ''}`}
            onClick={() => changeLanguage('nl')}
          >
            NL
          </button>
          <button 
            className={`lang-btn ${language === 'en' ? 'active' : ''}`}
            onClick={() => changeLanguage('en')}
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
            <p>{t('middlePanel.placeholder')}</p>
          </div>
        </div>
        <div className="right-panel">
          {/* Todo: Connections panel */}
          <div className="placeholder-panel">
            <p>{t('rightPanel.placeholder')}</p>
          </div>
        </div>
      </main>
    </div>
  );
};

export default App;
