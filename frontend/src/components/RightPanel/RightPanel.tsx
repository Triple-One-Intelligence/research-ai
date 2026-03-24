import { useEffect, useState } from 'react';
import type { KeyboardEvent } from 'react';
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
const getEntityKey = (entity: { id: string; type: string }) => `${entity.type}:${entity.id}`;
const getErrorMessage = (error: unknown, fallback: string): string => {
  if (error instanceof Error && error.message) return error.message;
  return fallback;
};

type CursorSetter = (cursor: string | null) => void;
type BoolSetter = (value: boolean) => void;
type SectionKey = 'collaborators' | 'publications' | 'organizations' | 'members';
type SectionState = {
  nextCursor: string | null;
  hasMore: boolean;
  loading: boolean;
};

const createInitialPagination = (): Record<SectionKey, SectionState> => ({
  collaborators: { nextCursor: null, hasMore: false, loading: false },
  publications: { nextCursor: null, hasMore: false, loading: false },
  organizations: { nextCursor: null, hasMore: false, loading: false },
  members: { nextCursor: null, hasMore: false, loading: false },
});

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
  const [pagination, setPagination] = useState<Record<SectionKey, SectionState>>(createInitialPagination);
    
  const selectEntity = (entity: EntitySuggestion) => {
    onEntitySelect(entity);
  };
  const updateSection = (section: SectionKey, patch: Partial<SectionState>) => {
    setPagination((prev) => ({
      ...prev,
      [section]: { ...prev[section], ...patch },
    }));
  };

  const handleEntityKeyDown = (e: KeyboardEvent<HTMLLIElement>, entity: EntitySuggestion) => {
    if (e.key === 'Enter' || e.key === ' ') {
      e.preventDefault();
      selectEntity(entity);
    }
  };

  useEffect(() => {
    if (!selectedEntity) {
      setConnections(null);
      setError(null);
      setPagination(createInitialPagination());
      setLoading(false);
      return;
    }

    let cancelled = false;
    setLoading(true);
    setError(null);

    fetchConnections(selectedEntity, PAGE_SIZE)
      .then((data) => {
        if (cancelled) return;
        setConnections(data);
        setPagination({
          collaborators: {
            loading: false,
            hasMore: data.collaborators_cursor != null,
            nextCursor: data.collaborators_cursor,
          },
          publications: {
            loading: false,
            hasMore: data.publications_cursor != null,
            nextCursor: data.publications_cursor,
          },
          organizations: {
            loading: false,
            hasMore: data.organizations_cursor != null,
            nextCursor: data.organizations_cursor,
          },
          members: {
            loading: false,
            hasMore: data.members_cursor != null,
            nextCursor: data.members_cursor,
          },
        });
      })
      .catch((err) => {
        if (!cancelled) setError(getErrorMessage(err, t('rightPanel.loadFailed')));
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    return () => { cancelled = true; };
  }, [selectedEntity]);

  const loadMoreConnections = async <
    TPage extends { cursor: string | null },
  >(args: {
    hasMore: boolean;
    loading: boolean;
    cursor: string | null;
    setLoading: BoolSetter;
    setHasMore: BoolSetter;
    setCursor: CursorSetter;
    fetchPage: (entity: EntitySuggestion, cursor: string | null) => Promise<TPage>;
    merge: (prev: ConnectionsResponse, page: TPage) => ConnectionsResponse;
  }) => {
    if (!selectedEntity || args.loading || !args.hasMore) return;
    const requestEntityKey = getEntityKey(selectedEntity);
    args.setLoading(true);
    setError(null);
    try {
      const page = await args.fetchPage(selectedEntity, args.cursor);
      setConnections((prev) => {
        if (!prev || getEntityKey({ id: prev.entity_id, type: prev.entity_type }) !== requestEntityKey) {
          return prev;
        }
        return args.merge(prev, page);
      });
      args.setHasMore(page.cursor != null);
      args.setCursor(page.cursor);
    } catch (err: unknown) {
      setError(getErrorMessage(err, t('rightPanel.loadFailed')));
    } finally {
      args.setLoading(false);
    }
  };

  const onLoadMore = async (sectionKey: SectionKey): Promise<void> => {
    const section = pagination[sectionKey];
    const commonArgs = {
      hasMore: section.hasMore,
      loading: section.loading,
      cursor: section.nextCursor,
      setLoading: (value: boolean) => updateSection(sectionKey, { loading: value }),
      setHasMore: (value: boolean) => updateSection(sectionKey, { hasMore: value }),
      setCursor: (value: string | null) => updateSection(sectionKey, { nextCursor: value }),
    };

    switch (sectionKey) {
      case 'collaborators':
        await loadMoreConnections({
          ...commonArgs,
          fetchPage: (entity, cursor) => fetchCollaboratorsPage(entity, PAGE_SIZE, cursor),
          merge: (prev, page) => ({ ...prev, collaborators: [...prev.collaborators, ...page.collaborators] }),
        });
        return;
      case 'publications':
        await loadMoreConnections({
          ...commonArgs,
          fetchPage: (entity, cursor) => fetchPublicationsPage(entity, PAGE_SIZE, cursor),
          merge: (prev, page) => ({ ...prev, publications: [...prev.publications, ...page.publications] }),
        });
        return;
      case 'organizations':
        await loadMoreConnections({
          ...commonArgs,
          fetchPage: (entity, cursor) => fetchOrganizationsPage(entity, PAGE_SIZE, cursor),
          merge: (prev, page) => ({ ...prev, organizations: [...prev.organizations, ...page.organizations] }),
        });
        return;
      case 'members':
        await loadMoreConnections({
          ...commonArgs,
          fetchPage: (entity, cursor) => fetchMembersPage(entity, PAGE_SIZE, cursor),
          merge: (prev, page) => ({ ...prev, members: [...prev.members, ...page.members] }),
        });
        return;
      default:
        return;
    }
  };

  const onLoadMoreCollaborators = async (): Promise<void> => onLoadMore('collaborators');
  const onLoadMorePublications = async (): Promise<void> => onLoadMore('publications');
  const onLoadMoreOrganizations = async (): Promise<void> => onLoadMore('organizations');
  const onLoadMoreMembers = async (): Promise<void> => onLoadMore('members');

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
        {pagination.collaborators.hasMore && (
          <div className="load-more-row">
            <button
              className="load-more-btn"
              onClick={onLoadMoreCollaborators}
              disabled={pagination.collaborators.loading}
            >
              {pagination.collaborators.loading ? t('rightPanel.loadingMore') : t('rightPanel.loadMore')}
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
        {pagination.publications.hasMore && (
          <div className="load-more-row">
            <button
              className="load-more-btn"
              onClick={onLoadMorePublications}
              disabled={pagination.publications.loading}
            >
              {pagination.publications.loading ? t('rightPanel.loadingMore') : t('rightPanel.loadMore')}
            </button>
          </div>
        )}
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
        {pagination.organizations.hasMore && (
          <div className="load-more-row">
            <button
              className="load-more-btn"
              onClick={onLoadMoreOrganizations}
              disabled={pagination.organizations.loading}
            >
              {pagination.organizations.loading ? t('rightPanel.loadingMore') : t('rightPanel.loadMore')}
            </button>
          </div>
        )}
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
        {pagination.members.hasMore && (
          <div className="load-more-row">
            <button
              className="load-more-btn"
              onClick={onLoadMoreMembers}
              disabled={pagination.members.loading}
            >
              {pagination.members.loading ? t('rightPanel.loadingMore') : t('rightPanel.loadMore')}
            </button>
          </div>
        )}
      </CollapsibleCard>
    </aside>
  );
};

export default RightPanel;
