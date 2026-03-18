import { useEffect, useState } from 'react';
import type {
  EntitySuggestion,
  ConnectionsResponse,
  PublicationVersion,
} from '../../types';
import {
  fetchConnections,
  fetchCollaboratorsPage,
  fetchPublicationsPage,
  fetchOrganizationsPage,
  fetchMembersPage,
} from '../../api';
import CollapsibleCard from './CollapsibleCard';
import './RightPanel.css';
import { useTranslation } from 'react-i18next';

const PAGE_SIZE = 10;

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
}

const RightPanel = ({ selectedEntity }: RightPanelProps) => {
  const [connections, setConnections] = useState<ConnectionsResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const { t } = useTranslation();

  const [collaboratorsNextCursor, setCollaboratorsNextCursor] = useState<string | null>(null);
  const [collaboratorsHasMore, setCollaboratorsHasMore] = useState(false);
  const [collaboratorsLoading, setCollaboratorsLoading] = useState(false);

  const [publicationsNextCursor, setPublicationsNextCursor] = useState<string | null>(null);
  const [publicationsHasMore, setPublicationsHasMore] = useState(false);
  const [publicationsLoading, setPublicationsLoading] = useState(false);

  const [organizationsNextCursor, setOrganizationsNextCursor] = useState<string | null>(null);
  const [organizationsHasMore, setOrganizationsHasMore] = useState(false);
  const [organizationsLoading, setOrganizationsLoading] = useState(false);

  const [membersNextCursor, setMembersNextCursor] = useState<string | null>(null);
  const [membersHasMore, setMembersHasMore] = useState(false);
  const [membersLoading, setMembersLoading] = useState(false);

  useEffect(() => {
    if (!selectedEntity) {
      setConnections(null);
      setError(null);
      setCollaboratorsNextCursor(null);
      setCollaboratorsHasMore(false);
      setCollaboratorsLoading(false);
      setPublicationsNextCursor(null);
      setPublicationsHasMore(false);
      setPublicationsLoading(false);
      setOrganizationsNextCursor(null);
      setOrganizationsHasMore(false);
      setOrganizationsLoading(false);
      setMembersNextCursor(null);
      setMembersHasMore(false);
      setMembersLoading(false);
      return;
    }

    let cancelled = false;
    setLoading(true);
    setError(null);

    fetchConnections(selectedEntity, PAGE_SIZE)
      .then((data) => {
        if (!cancelled) setConnections(data);
        if (cancelled) return;

        const nextCollab = data.collaborators.length === PAGE_SIZE
          ? data.collaborators[data.collaborators.length - 1].author_id
          : null;
        setCollaboratorsHasMore(data.collaborators.length === PAGE_SIZE);
        setCollaboratorsNextCursor(nextCollab);

        const nextPubs = data.publications.length === PAGE_SIZE
          ? data.publications[data.publications.length - 1].doi
          : null;
        setPublicationsHasMore(data.publications.length === PAGE_SIZE);
        setPublicationsNextCursor(nextPubs);

        const nextOrgs = data.organizations.length === PAGE_SIZE
          ? data.organizations[data.organizations.length - 1].organization_id
          : null;
        setOrganizationsHasMore(data.organizations.length === PAGE_SIZE);
        setOrganizationsNextCursor(nextOrgs);

        const nextMembers = data.members.length === PAGE_SIZE
          ? data.members[data.members.length - 1].author_id
          : null;
        setMembersHasMore(data.members.length === PAGE_SIZE);
        setMembersNextCursor(nextMembers);
      })
      .catch((err) => {
        if (!cancelled) setError(err.message ?? t('rightPanel.loadFailedFallback'));
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    return () => { cancelled = true; };
  }, [selectedEntity]);

  const mergeUniqueById = <T,>(
    existing: T[],
    incoming: T[],
    getId: (item: T) => string,
  ): { merged: T[]; addedCount: number } => {
    const existingIds = new Set(existing.map(getId));
    const uniqueNew = incoming.filter((i) => !existingIds.has(getId(i)));
    return { merged: [...existing, ...uniqueNew], addedCount: uniqueNew.length };
  };

  const onLoadMoreCollaborators = async () => {
    if (!selectedEntity || collaboratorsLoading || !collaboratorsHasMore) return;
    setCollaboratorsLoading(true);
    setError(null);
    try {
      const page = await fetchCollaboratorsPage(selectedEntity, PAGE_SIZE, collaboratorsNextCursor);
      setConnections((prev) => {
        if (!prev) return prev;
        const { merged, addedCount } = mergeUniqueById(
          prev.collaborators,
          page.collaborators,
          (p) => p.author_id,
        );
        const shouldContinue = addedCount > 0 && page.next_cursor != null;
        setCollaboratorsHasMore(shouldContinue);
        setCollaboratorsNextCursor(page.next_cursor);
        return { ...prev, collaborators: merged };
      });
    } catch (err: any) {
      setError(err?.message ?? t('rightPanel.loadFailedFallback'));
    } finally {
      setCollaboratorsLoading(false);
    }
  };

  const onLoadMorePublications = async () => {
    if (!selectedEntity || publicationsLoading || !publicationsHasMore) return;
    setPublicationsLoading(true);
    setError(null);
    try {
      const page = await fetchPublicationsPage(selectedEntity, PAGE_SIZE, publicationsNextCursor);
      setConnections((prev) => {
        if (!prev) return prev;
        const { merged, addedCount } = mergeUniqueById(
          prev.publications,
          page.publications,
          (p) => p.doi,
        );
        const shouldContinue = addedCount > 0 && page.next_cursor != null;
        setPublicationsHasMore(shouldContinue);
        setPublicationsNextCursor(page.next_cursor);
        return { ...prev, publications: merged };
      });
    } catch (err: any) {
      setError(err?.message ?? t('rightPanel.loadFailedFallback'));
    } finally {
      setPublicationsLoading(false);
    }
  };

  const onLoadMoreOrganizations = async () => {
    if (!selectedEntity || organizationsLoading || !organizationsHasMore) return;
    setOrganizationsLoading(true);
    setError(null);
    try {
      const page = await fetchOrganizationsPage(selectedEntity, PAGE_SIZE, organizationsNextCursor);
      setConnections((prev) => {
        if (!prev) return prev;
        const { merged, addedCount } = mergeUniqueById(
          prev.organizations,
          page.organizations,
          (o) => o.organization_id,
        );
        const shouldContinue = addedCount > 0 && page.next_cursor != null;
        setOrganizationsHasMore(shouldContinue);
        setOrganizationsNextCursor(page.next_cursor);
        return { ...prev, organizations: merged };
      });
    } catch (err: any) {
      setError(err?.message ?? t('rightPanel.loadFailedFallback'));
    } finally {
      setOrganizationsLoading(false);
    }
  };

  const onLoadMoreMembers = async () => {
    if (!selectedEntity || membersLoading || !membersHasMore) return;
    setMembersLoading(true);
    setError(null);
    try {
      const page = await fetchMembersPage(selectedEntity, PAGE_SIZE, membersNextCursor);
      setConnections((prev) => {
        if (!prev) return prev;
        const { merged, addedCount } = mergeUniqueById(
          prev.members,
          page.members,
          (m) => m.author_id,
        );
        const shouldContinue = addedCount > 0 && page.next_cursor != null;
        setMembersHasMore(shouldContinue);
        setMembersNextCursor(page.next_cursor);
        return { ...prev, members: merged };
      });
    } catch (err: any) {
      setError(err?.message ?? t('rightPanel.loadFailedFallback'));
    } finally {
      setMembersLoading(false);
    }
  };

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
              <span title={p.name}>{p.name}</span>
            </li>
          ))}
        </ul>
        {collaboratorsHasMore && (
          <div className="load-more-row">
            <button
              className="load-more-btn"
              onClick={onLoadMoreCollaborators}
              disabled={collaboratorsLoading}
            >
              {collaboratorsLoading ? 'Loading...' : 'Load more'}
            </button>
          </div>
        )}
      </CollapsibleCard>

      <CollapsibleCard title={t('rightPanel.publications')} count={connections.publications.length} defaultOpen>
        <ul className="connection-list">
          {connections.publications.map((pub) => (
            <PublicationItem key={pub.doi} pub={pub} />
          ))}
        </ul>
        {publicationsHasMore && (
          <div className="load-more-row">
            <button
              className="load-more-btn"
              onClick={onLoadMorePublications}
              disabled={publicationsLoading}
            >
              {publicationsLoading ? 'Loading...' : 'Load more'}
            </button>
          </div>
        )}
      </CollapsibleCard>

      <CollapsibleCard title={t('rightPanel.organizations')} count={connections.organizations.length}>
        <ul className="connection-list">
          {connections.organizations.map((org) => (
            <li key={org.organization_id} className="connection-item organization">
              <span className="entity-type-badge organization">🏛️</span>
              <span title={org.name}>{org.name}</span>
            </li>
          ))}
        </ul>
        {organizationsHasMore && (
          <div className="load-more-row">
            <button
              className="load-more-btn"
              onClick={onLoadMoreOrganizations}
              disabled={organizationsLoading}
            >
              {organizationsLoading ? 'Loading...' : 'Load more'}
            </button>
          </div>
        )}
      </CollapsibleCard>

      <CollapsibleCard title={t('rightPanel.members')} count={connections.members.length}>
        <ul className="connection-list">
          {connections.members.map((m) => (
            <li key={m.author_id} className="connection-item person">
              <span className="entity-type-badge person">👤</span>
              <div className="member-info">
                <span title={m.name}>{m.name}</span>
              </div>
            </li>
          ))}
        </ul>
        {membersHasMore && (
          <div className="load-more-row">
            <button
              className="load-more-btn"
              onClick={onLoadMoreMembers}
              disabled={membersLoading}
            >
              {membersLoading ? 'Loading...' : 'Load more'}
            </button>
          </div>
        )}
      </CollapsibleCard>
    </aside>
  );
};

export default RightPanel;
