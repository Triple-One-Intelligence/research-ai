import { useState, useEffect } from 'react';
import type { EntitySuggestion, ConnectionsResponse } from '../../types';
import { fetchConnections } from '../../api';
import CollapsibleCard from './CollapsibleCard';
import './RightPanel.css';

interface RightPanelProps {
  selectedEntity: EntitySuggestion | null;
}

const RightPanel = ({ selectedEntity }: RightPanelProps) => {
  const [connections, setConnections] = useState<ConnectionsResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

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
        if (!cancelled) setError(err.message ?? 'Failed to load connections');
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
          <p>Select an entity to see connections</p>
        </div>
      </aside>
    );
  }

  if (loading) {
    return (
      <aside className="right-panel">
        <div className="right-panel-loading">
          <span className="search-spinner" />
          Loading connections...
        </div>
      </aside>
    );
  }

  if (error) {
    return (
      <aside className="right-panel">
        <div className="right-panel-error">
          <p>Failed to load connections.</p>
          <p className="right-panel-error-detail">{error}</p>
        </div>
      </aside>
    );
  }

  if (!connections) return null;

  return (
    <aside className="right-panel">
      <h2 className="right-panel-title">Connections</h2>

      <CollapsibleCard title="Collaborators" count={connections.collaborators.length} defaultOpen>
        <ul className="connection-list">
          {connections.collaborators.map((p) => (
            <li key={p.author_id} className="connection-item person">
              <span className="entity-type-badge person">👤</span>
              <span>{p.name}</span>
            </li>
          ))}
        </ul>
      </CollapsibleCard>

      <CollapsibleCard title="Publications" count={connections.publications.length} defaultOpen>
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

      <CollapsibleCard title="Organizations" count={connections.organizations.length}>
        <ul className="connection-list">
          {connections.organizations.map((org) => (
            <li key={org.organization_id} className="connection-item organization">
              <span className="entity-type-badge organization">🏛️</span>
              <span>{org.name}</span>
            </li>
          ))}
        </ul>
      </CollapsibleCard>

      <CollapsibleCard title="Members" count={connections.members.length}>
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
