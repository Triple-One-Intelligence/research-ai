import { useEffect, useState } from 'react';
import type { KeyboardEvent } from 'react';
import type { EntitySuggestion, ConnectionsResponse, PublicationVersion } from '../../types';
import { fetchConnections } from '../../api';
import CollapsibleCard from './CollapsibleCard';
import './RightPanel.css';
import { useTranslation } from 'react-i18next';

// Right column: fetches and displays "connections" for the currently selected entity.
// Results are grouped into collapsible sections (collaborators, publications, organizations, members).
/* ── Inline sub-component for a single publication ────────────── */

function PublicationItem({ pub }: { pub: ConnectionsResponse['publications'][number] }) {
  const { t } = useTranslation();
  const versions = pub.versions;
  const hasVersions = versions != null && versions.length > 1;

  return (
    <li className="connection-item publication">
      <div className="publication-info">
        <span className="publication-title" title={pub.title ?? pub.doi}>{pub.title ?? pub.doi}</span>
        <span className="publication-meta">
          {[pub.year, pub.category].filter(Boolean).join(' \u00b7 ')}
        </span>
        {hasVersions ? (
          <details className="versions-card">
            <summary className="versions-card-header">
              <span>{t('rightPanel.versions', { count: versions.length })}</span>
              <span className="collapsible-card-count">{versions.length}</span>
            </summary>
            <ul className="versions-list">
              {versions.map((v: PublicationVersion) => (
                <li key={v.doi} className="version-item">
                  <a
                    href={`https://doi.org/${v.doi}`}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="version-doi"
                  >
                    {v.doi}
                  </a>
                  <span className="publication-meta">
                    {[v.year, v.category].filter(Boolean).join(' \u00b7 ')}
                  </span>
                </li>
              ))}
            </ul>
          </details>
        ) : (
          <a
            href={`https://doi.org/${pub.doi}`}
            target="_blank"
            rel="noopener noreferrer"
            className="version-doi"
          >
            {pub.doi}
          </a>
        )}
      </div>
    </li>
  );
}

/* ── Main component ───────────────────────────────────────────── */

interface RightPanelProps {
  selectedEntity: EntitySuggestion | null;
  onEntitySelect: (entity: EntitySuggestion) => void;
}

const RightPanel = ({ selectedEntity, onEntitySelect }: RightPanelProps) => {
  const [connections, setConnections] = useState<ConnectionsResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const { t } = useTranslation();

  const selectEntity = (entity: EntitySuggestion) => {
    onEntitySelect(entity);
  };

  const handleEntityKeyDown = (e: KeyboardEvent<HTMLLIElement>, entity: EntitySuggestion) => {
    if (e.key === 'Enter' || e.key === ' ') {
      e.preventDefault();
      selectEntity(entity);
    }
  };

  useEffect(() => {
    if (!selectedEntity) {
      // Avoid synchronous state updates inside effects (lint rule). This branch runs
      // when switching away from an entity; a microtask keeps the update responsive.
      Promise.resolve().then(() => {
        setConnections(null);
        setError(null);
      });
      return;
    }

    let cancelled = false;
    Promise.resolve().then(() => {
      if (!cancelled) {
        setLoading(true);
        setError(null);
      }
    });

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
  }, [selectedEntity, t]);

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
            <li
              key={p.author_id}
              className="connection-item person clickable"
              role="button"
              tabIndex={0}
              onClick={() => selectEntity({ id: p.author_id, type: 'person', label: p.name })}
              onKeyDown={(e) => handleEntityKeyDown(e, { id: p.author_id, type: 'person', label: p.name })}
            >
              <span className="entity-type-badge person">👤</span>
              <span title={p.name}>{p.name}</span>
            </li>
          ))}
        </ul>
      </CollapsibleCard>

      <CollapsibleCard title={t('rightPanel.publications')} count={connections.publications.length} defaultOpen>
        <ul className="connection-list">
          {connections.publications.map((pub) => (
            <PublicationItem key={pub.doi} pub={pub} />
          ))}
        </ul>
      </CollapsibleCard>

      <CollapsibleCard title={t('rightPanel.organizations')} count={connections.organizations.length}>
        <ul className="connection-list">
          {connections.organizations.map((org) => (
            <li
              key={org.organization_id}
              className="connection-item organization clickable"
              role="button"
              tabIndex={0}
              onClick={() => selectEntity({ id: org.organization_id, type: 'organization', label: org.name })}
              onKeyDown={(e) =>
                handleEntityKeyDown(e, { id: org.organization_id, type: 'organization', label: org.name })
              }
            >
              <span className="entity-type-badge organization">🏛️</span>
              <span title={org.name}>{org.name}</span>
            </li>
          ))}
        </ul>
      </CollapsibleCard>

      <CollapsibleCard title={t('rightPanel.members')} count={connections.members.length}>
        <ul className="connection-list">
          {connections.members.map((m) => (
            <li
              key={m.author_id}
              className="connection-item person clickable"
              role="button"
              tabIndex={0}
              onClick={() => selectEntity({ id: m.author_id, type: 'person', label: m.name })}
              onKeyDown={(e) => handleEntityKeyDown(e, { id: m.author_id, type: 'person', label: m.name })}
            >
              <span className="entity-type-badge person">👤</span>
              <div className="member-info">
                <span title={m.name}>{m.name}</span>
              </div>
            </li>
          ))}
        </ul>
      </CollapsibleCard>
    </aside>
  );
};

export default RightPanel;
