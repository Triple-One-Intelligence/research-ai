import { useState, useEffect } from 'react';
import type { EntitySuggestion, ConnectionsResponse } from '../../types';
import { fetchConnections } from '../../apiconnection/api';
import CollapsibleCard from './CollapsibleCard';
import './RightPanel.css';
import { useTranslation } from 'react-i18next';

interface RightPanelProps {
  selectedEntity: EntitySuggestion | null;
}

const RightPanel = ({ selectedEntity }: RightPanelProps) => {
  const [connections, setConnections] = useState<ConnectionsResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const { t } = useTranslation();

  useEffect(() => {
    if (!selectedEntity) {
      setConnections(null);
      setError(null);
      return;
    }

    let cancelled = false;
    setLoading(true);
    setError(null);

    fetchConnections(selectedEntity)
      .then((data) => {
        if (!cancelled) setConnections(data);
      })
      .catch((err) => {
        if (!cancelled) setError(err.message ?? t('rightPanel.loadFailedFallback'));
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    return () => { cancelled = true; };
  }, [selectedEntity]);

  if (!selectedEntity) {
    return (
      <aside className="right-panel">
        <div className="placeholder-panel">
          <p>{t('rightPanel.selectEntity')}</p>
        </div>
      </aside>
    );
  }

  if (loading) {
    return (
      <aside className="right-panel">
        <div className="right-panel-loading">
          <span className="search-spinner" />
          {t('rightPanel.loadingConnections')}
        </div>
      </aside>
    );
  }

  if (error) {
    return (
      <aside className="right-panel">
        <div className="right-panel-error">
          <p>{t('rightPanel.loadFailed')}</p>
          <p className="right-panel-error-detail">{error}</p>
        </div>
      </aside>
    );
  }

  if (!connections) return null;

  return (
    <aside className="right-panel">
      <h2 className="right-panel-title">{t('rightPanel.title')}</h2>

      <CollapsibleCard title={t('rightPanel.collaborators')} count={connections.collaborators.length} defaultOpen>
        <ul className="connection-list">
          {connections.collaborators.map((p) => (
            <li key={p.author_id} className="connection-item person">
              <span className="entity-type-badge person">👤</span>
              <span>{p.name}</span>
            </li>
          ))}
        </ul>
      </CollapsibleCard>

      <CollapsibleCard title={t('rightPanel.publications')} count={connections.publications.length} defaultOpen>
        <ul className="connection-list">
          {connections.publications.map((pub) => (
            <li key={pub.doi} className="connection-item publication">
              <div className="publication-info">
                <span className="publication-title">{pub.title ?? pub.doi}</span>
                <span className="publication-meta">
                  {[pub.year, pub.category].filter(Boolean).join(' \u00b7 ')}
                </span>
              </div>
            </li>
          ))}
        </ul>
      </CollapsibleCard>

      <CollapsibleCard title={t('rightPanel.organizations')} count={connections.organizations.length}>
        <ul className="connection-list">
          {connections.organizations.map((org) => (
            <li key={org.organization_id} className="connection-item organization">
              <span className="entity-type-badge organization">🏛️</span>
              <span>{org.name}</span>
            </li>
          ))}
        </ul>
      </CollapsibleCard>

      <CollapsibleCard title={t('rightPanel.members')} count={connections.members.length}>
        <ul className="connection-list">
          {connections.members.map((m) => (
            <li key={m.author_id} className="connection-item person">
              <span className="entity-type-badge person">👤</span>
              <div className="member-info">
                <span>{m.name}</span>
                {m.role && <span className="member-role">{m.role}</span>}
              </div>
            </li>
          ))}
        </ul>
      </CollapsibleCard>
    </aside>
  );
};

export default RightPanel;
