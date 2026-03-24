import {
  useCallback,
  useEffect,
  useMemo,
  useState,
  type ChangeEvent,
  type KeyboardEvent,
  type MouseEvent,
  type ReactNode,
} from 'react';
import { useTranslation } from 'react-i18next';
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
import { IconCopy, IconExternalLink, IconOrganization, IconPerson } from './RightPanelIcons';
import {
  clampPublicationYearInput,
  filterPublications,
  parsePublicationFilterYearInput,
  parseYearInput,
  sortByName,
  sortPublications,
  type NameSort,
  type PublicationsSort,
} from './rightPanelUtils';
import './RightPanel.css';

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

const defaultSectionOpen = {
  collaborators: false,
  publications: false,
  organizations: false,
};

type SectionOptionsPanelProps = {
  summary: string;
  children: ReactNode;
  className?: string;
};

function SectionOptionsPanel({ summary, children, className }: SectionOptionsPanelProps) {
  const rootClass = className
    ? `right-panel-section-options ${className}`
    : 'right-panel-section-options';
  return (
    <details className={rootClass}>
      <summary className="right-panel-section-options-summary">{summary}</summary>
      <div className="right-panel-section-options-body">{children}</div>
    </details>
  );
}

function DoiRow({ doi }: { doi: string }) {
  const { t } = useTranslation();
  const [copied, setCopied] = useState(false);
  const href = `https://doi.org/${doi}`;

  useEffect(() => {
    if (!copied) return;
    const id = window.setTimeout(() => setCopied(false), 2000);
    return () => window.clearTimeout(id);
  }, [copied]);

  const handleCopy = useCallback(async () => {
    try {
      await navigator.clipboard.writeText(doi);
      setCopied(true);
    } catch {
      /* ignore */
    }
  }, [doi]);

  return (
    <div className="doi-row">
      <a
        href={href}
        target="_blank"
        rel="noopener noreferrer"
        className="version-doi"
      >
        {doi}
      </a>
      <div className="doi-actions">
        <button
          type="button"
          className="doi-icon-btn"
          onClick={handleCopy}
          aria-label={t('rightPanel.copyDoi')}
          title={t('rightPanel.copyDoi')}
        >
          <IconCopy />
        </button>
        <a
          href={href}
          target="_blank"
          rel="noopener noreferrer"
          className="doi-icon-btn"
          aria-label={t('rightPanel.openDoiNewTab')}
          title={t('rightPanel.openDoiNewTab')}
        >
          <IconExternalLink />
        </a>
      </div>
      {copied ? <span className="doi-copied" role="status">{t('rightPanel.doiCopied')}</span> : null}
    </div>
  );
}

function PublicationItem({ pub }: { pub: ConnectionsResponse['publications'][number] }) {
  const { t } = useTranslation();
  const versions = pub.versions;
  const hasVersions = versions != null && versions.length > 1;

  return (
    <li className="connection-item publication">
      <div className="publication-info">
        <span className="publication-title" title={pub.title ?? pub.doi}>{pub.title ?? pub.doi}</span>
        <span className="publication-meta">
          {[pub.year, pub.category].filter(Boolean).join(' · ')}
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
                  <DoiRow doi={v.doi} />
                  <span className="publication-meta">
                    {[v.year, v.category].filter(Boolean).join(' · ')}
                  </span>
                </li>
              ))}
            </ul>
          </details>
        ) : (
          <DoiRow doi={pub.doi} />
        )}
      </div>
    </li>
  );
}

interface RightPanelProps {
  selectedEntity: EntitySuggestion | null;
  onEntitySelect: (entity: EntitySuggestion) => void;
}

const RightPanel = ({ selectedEntity, onEntitySelect }: RightPanelProps) => {
  const { t } = useTranslation();
  const [connections, setConnections] = useState<ConnectionsResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [pagination, setPagination] = useState<Record<SectionKey, SectionState>>(createInitialPagination);
  const [fetchNonce, setFetchNonce] = useState(0);
  const [pubYearFromRaw, setPubYearFromRaw] = useState('');
  const [pubYearToRaw, setPubYearToRaw] = useState('');
  const [collaboratorsNameSort, setCollaboratorsNameSort] = useState<NameSort>('name_asc');
  const [organizationsNameSort, setOrganizationsNameSort] = useState<NameSort>('name_asc');
  const [publicationsSort, setPublicationsSort] = useState<PublicationsSort>('year_desc');
  const [sectionOpen, setSectionOpen] = useState(() => ({ ...defaultSectionOpen }));

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
    // Reset UI state when entity changes
    setSectionOpen({ ...defaultSectionOpen });
    setPubYearFromRaw('');
    setPubYearToRaw('');
    setCollaboratorsNameSort('name_asc');
    setOrganizationsNameSort('name_asc');
    setPublicationsSort('year_desc');
  }, [selectedEntity]);

  useEffect(() => {
    if (!selectedEntity) return;

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

    return () => {
      cancelled = true;
    };
  }, [selectedEntity, fetchNonce, t]);

  const handleRetry = useCallback(() => {
    setFetchNonce((n) => n + 1);
  }, []);

  const setOpen = (key: keyof typeof defaultSectionOpen) => (open: boolean) => {
    setSectionOpen((prev) => ({ ...prev, [key]: open }));
  };

  const maxPublicationYear = new Date().getFullYear();

  const handlePubYearFromChange = useCallback(
    (e: ChangeEvent<HTMLInputElement>) => {
      setPubYearFromRaw(clampPublicationYearInput(e.target.value, maxPublicationYear));
    },
    [maxPublicationYear],
  );

  const handlePubYearToChange = useCallback(
    (e: ChangeEvent<HTMLInputElement>) => {
      const nextRaw = clampPublicationYearInput(e.target.value, maxPublicationYear);
      const nextYearTo = parsePublicationFilterYearInput(nextRaw);
      const currentYearFrom = parsePublicationFilterYearInput(pubYearFromRaw);

      if (nextYearTo != null && currentYearFrom != null && nextYearTo < currentYearFrom) {
        setPubYearToRaw(String(currentYearFrom));
        return;
      }

      setPubYearToRaw(nextRaw);
    },
    [maxPublicationYear, pubYearFromRaw],
  );

  const handlePubYearKeyDown = useCallback(
    (field: 'from' | 'to') => (e: KeyboardEvent<HTMLInputElement>) => {
      if (e.key !== 'ArrowDown') return;

      const currentValue = field === 'from' ? pubYearFromRaw : pubYearToRaw;
      if (parseYearInput(currentValue) !== 0) return;

      e.preventDefault();
      const nextValue = String(maxPublicationYear);
      if (field === 'from') setPubYearFromRaw(nextValue);
      else setPubYearToRaw(nextValue);
    },
    [maxPublicationYear, pubYearFromRaw, pubYearToRaw],
  );

  const handlePubYearSpinnerMouseDown = useCallback(
    (field: 'from' | 'to') => (e: MouseEvent<HTMLInputElement>) => {
      const input = e.currentTarget;
      const currentValue = field === 'from' ? pubYearFromRaw : pubYearToRaw;
      if (parseYearInput(currentValue) !== 0) return;

      const rect = input.getBoundingClientRect();
      const spinnerZoneWidth = 24;
      const clickedSpinner = e.clientX >= rect.right - spinnerZoneWidth;
      const clickedDownControl = e.clientY >= rect.top + rect.height / 2;

      if (!clickedSpinner || !clickedDownControl) return;

      e.preventDefault();
      const nextValue = String(maxPublicationYear);
      if (field === 'from') setPubYearFromRaw(nextValue);
      else setPubYearToRaw(nextValue);
    },
    [maxPublicationYear, pubYearFromRaw, pubYearToRaw],
  );

  const pubYearFrom = useMemo(() => parsePublicationFilterYearInput(pubYearFromRaw), [pubYearFromRaw]);
  const pubYearTo = useMemo(() => parsePublicationFilterYearInput(pubYearToRaw), [pubYearToRaw]);

  const includeUnknownYear = pubYearFrom == null && pubYearTo == null;

  const sortedAndFilteredPublications = useMemo(() => {
    if (!connections) return [];
    const filtered = filterPublications(
      connections.publications,
      '',
      pubYearFrom,
      pubYearTo,
      includeUnknownYear,
    );
    return sortPublications(filtered, publicationsSort);
  }, [connections, pubYearFrom, pubYearTo, includeUnknownYear, publicationsSort]);

  const peopleItems = useMemo(() => {
    if (!connections) return [];
    return connections.entity_type === 'organization' ? connections.members : connections.collaborators;
  }, [connections]);

  const sortedCollaborators = useMemo(() => {
    return sortByName(peopleItems, collaboratorsNameSort);
  }, [peopleItems, collaboratorsNameSort]);

  const sortedOrganizations = useMemo(() => {
    if (!connections) return [];
    return sortByName(connections.organizations, organizationsNameSort);
  }, [connections, organizationsNameSort]);

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
      <aside className="right-panel" aria-busy="true" aria-label={t('rightPanel.loadingConnections')}>
        <div className="right-panel-skeleton">
          <div className="right-panel-skeleton-header">
            <div className="skeleton-block skeleton-chip" />
            <div className="skeleton-block skeleton-line-title" />
          </div>
          <div className="skeleton-block skeleton-line" />
          <div className="skeleton-block skeleton-line" />
          <div className="skeleton-block skeleton-line skeleton-line--short" />
          <div className="skeleton-block skeleton-card" />
          <div className="skeleton-block skeleton-card" />
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
          <button type="button" className="right-panel-retry" onClick={handleRetry}>
            {t('rightPanel.retry')}
          </button>
        </div>
      </aside>
    );
  }

  if (!connections) return null;

  const entityTypeLabel =
    connections.entity_type === 'organization'
      ? t('rightPanel.entityTypeOrganization')
      : t('rightPanel.entityTypePerson');

  const sectionOptionsSummary = t('rightPanel.sectionListOptions');

  const collaboratorsLeading = (
    <SectionOptionsPanel summary={sectionOptionsSummary}>
      <label className="right-panel-section-field">
        <span>{t('rightPanel.sortCollaborators')}</span>
        <select
          className="right-panel-sort-select right-panel-sort-select--block"
          value={collaboratorsNameSort}
          onChange={(e) => setCollaboratorsNameSort(e.target.value as NameSort)}
        >
          <option value="name_asc">{t('rightPanel.nameAsc')}</option>
          <option value="name_desc">{t('rightPanel.nameDesc')}</option>
        </select>
      </label>
    </SectionOptionsPanel>
  );

  const publicationsLeading = (
    <SectionOptionsPanel summary={sectionOptionsSummary}>
      <label className="right-panel-section-field">
        <span>{t('rightPanel.sortPublications')}</span>
        <select
          className="right-panel-sort-select right-panel-sort-select--block"
          value={publicationsSort}
          onChange={(e) => setPublicationsSort(e.target.value as PublicationsSort)}
        >
          <option value="year_desc">{t('rightPanel.sortYearDesc')}</option>
          <option value="year_asc">{t('rightPanel.sortYearAsc')}</option>
          <option value="title_asc">{t('rightPanel.sortTitleAsc')}</option>
          <option value="title_desc">{t('rightPanel.sortTitleDesc')}</option>
        </select>
      </label>
    </SectionOptionsPanel>
  );

  const organizationsLeading = (
    <SectionOptionsPanel summary={sectionOptionsSummary}>
      <label className="right-panel-section-field">
        <span>{t('rightPanel.sortOrganizations')}</span>
        <select
          className="right-panel-sort-select right-panel-sort-select--block"
          value={organizationsNameSort}
          onChange={(e) => setOrganizationsNameSort(e.target.value as NameSort)}
        >
          <option value="name_asc">{t('rightPanel.nameAsc')}</option>
          <option value="name_desc">{t('rightPanel.nameDesc')}</option>
        </select>
      </label>
    </SectionOptionsPanel>
  );

  return (
    <aside className="right-panel">
      <div className="right-panel-sticky-top">
        <div className="right-panel-entity-header">
          <span className={`entity-type-pill ${connections.entity_type === 'organization' ? 'entity-type-pill--organization' : 'entity-type-pill--person'}`}>
            {entityTypeLabel}
          </span>
          <h2 className="right-panel-entity-name" title={selectedEntity.label}>
            {selectedEntity.label}
          </h2>
          <p className="right-panel-subtitle">{t('rightPanel.title')}</p>
        </div>

        <div className="right-panel-toolbar">
          <SectionOptionsPanel
            summary={t('rightPanel.globalFilters')}
            className="right-panel-global-filter"
          >
            <div className="right-panel-global-year-fields">
              <label className="right-panel-section-field right-panel-year-field-row">
                <span>{t('rightPanel.yearFrom')}</span>
                <input
                  type="number"
                  className="right-panel-toolbar-input right-panel-toolbar-input--grow"
                  inputMode="numeric"
                  placeholder="-"
                  min={0}
                  max={maxPublicationYear}
                  value={pubYearFromRaw}
                  onChange={handlePubYearFromChange}
                  onKeyDown={handlePubYearKeyDown('from')}
                  onMouseDown={handlePubYearSpinnerMouseDown('from')}
                  aria-label={t('rightPanel.yearFrom')}
                />
              </label>
              <label className="right-panel-section-field right-panel-year-field-row">
                <span>{t('rightPanel.yearTo')}</span>
                <input
                  type="number"
                  className="right-panel-toolbar-input right-panel-toolbar-input--grow"
                  inputMode="numeric"
                  placeholder="-"
                  min={pubYearFrom ?? 0}
                  max={maxPublicationYear}
                  value={pubYearToRaw}
                  onChange={handlePubYearToChange}
                  onKeyDown={handlePubYearKeyDown('to')}
                  onMouseDown={handlePubYearSpinnerMouseDown('to')}
                  aria-label={t('rightPanel.yearTo')}
                />
              </label>
            </div>
          </SectionOptionsPanel>
        </div>
      </div>

      <CollapsibleCard
        title={t('rightPanel.collaborators')}
        totalCount={peopleItems.length}
        filteredCount={sortedCollaborators.length}
        open={sectionOpen.collaborators}
        onOpenChange={setOpen('collaborators')}
        emptyMessage={t('rightPanel.emptyCollaborators')}
        noMatchMessage={t('rightPanel.noFilterMatches')}
        leadingContent={collaboratorsLeading}
      >
        <ul className="connection-list">
          {sortedCollaborators.map((p) => (
            <li
              key={p.author_id}
              className="connection-item person clickable"
              role="button"
              tabIndex={0}
              onClick={() => selectEntity({ id: p.author_id, type: 'person', label: p.name })}
              onKeyDown={(e) => handleEntityKeyDown(e, { id: p.author_id, type: 'person', label: p.name })}
            >
              <span className="entity-type-badge person" aria-hidden>
                <IconPerson />
              </span>
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

      <CollapsibleCard
        title={t('rightPanel.publications')}
        totalCount={connections.publications.length}
        filteredCount={sortedAndFilteredPublications.length}
        open={sectionOpen.publications}
        onOpenChange={setOpen('publications')}
        emptyMessage={t('rightPanel.emptyPublications')}
        noMatchMessage={t('rightPanel.noFilterMatches')}
        leadingContent={publicationsLeading}
      >
        <ul className="connection-list">
          {sortedAndFilteredPublications.map((pub) => (
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

      <CollapsibleCard
        title={t('rightPanel.organizations')}
        totalCount={connections.organizations.length}
        filteredCount={sortedOrganizations.length}
        open={sectionOpen.organizations}
        onOpenChange={setOpen('organizations')}
        emptyMessage={t('rightPanel.emptyOrganizations')}
        noMatchMessage={t('rightPanel.noFilterMatches')}
        leadingContent={organizationsLeading}
      >
        <ul className="connection-list">
          {sortedOrganizations.map((org) => (
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
              <span className="entity-type-badge organization" aria-hidden>
                <IconOrganization />
              </span>
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
    </aside>
  );
};

export default RightPanel;
