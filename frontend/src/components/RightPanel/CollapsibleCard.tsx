import type { ReactNode } from 'react';

/**
 * Props for CollapsibleCard, describing the section label, counts and messages for empty/filter states.
 */
export interface CollapsibleCardProps {
  title: string;
  /** Full dataset size (before filter). */
  totalCount: number;
  /** Size after filter; used for badge and empty states. */
  filteredCount: number;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  /** Shown when `totalCount === 0`. */
  emptyMessage: string;
  /** Shown when filter hides all items but section has data. */
  noMatchMessage: string;
  /**
   * Optional block always shown at the top of the body when `totalCount > 0`
   * (e.g. per-section sort controls), including when the filtered list is empty
   * so users can change options without losing access.
   */
  leadingContent?: ReactNode;
  children: ReactNode;
}

/**
 * CollapsibleCard renders a reusable <details> section with a header, item count badge and body content.
 * It also shows helpful messages when there are no items at all, or when filtering hides all items.
 */
const CollapsibleCard = ({
  title,
  totalCount,
  filteredCount,
  open,
  onOpenChange,
  emptyMessage,
  noMatchMessage,
  leadingContent,
  children,
}: CollapsibleCardProps) => {
  const showFilterEmpty = totalCount > 0 && filteredCount === 0;
  const countsDiffer = filteredCount !== totalCount;

  return (
    <details
      className="collapsible-card"
      open={open}
      onToggle={(e) => onOpenChange(e.currentTarget.open)}
    >
      <summary className="collapsible-card-header">
        <span className="collapsible-card-title">{title}</span>
        <span className="collapsible-card-count-wrap">
          {countsDiffer ? (
            <span
              className="collapsible-card-count"
              title={`${filteredCount} / ${totalCount}`}
            >
              {filteredCount}
              <span className="collapsible-card-count-of">/{totalCount}</span>
            </span>
          ) : (
            <span className="collapsible-card-count">{totalCount}</span>
          )}
        </span>
      </summary>
      <div className="collapsible-card-body">
        {totalCount === 0 ? (
          <p className="collapsible-card-empty">{emptyMessage}</p>
        ) : (
          <>
            {leadingContent}
            {showFilterEmpty ? (
              <p className="collapsible-card-empty collapsible-card-empty--filter">{noMatchMessage}</p>
            ) : (
              children
            )}
          </>
        )}
      </div>
    </details>
  );
};

export default CollapsibleCard;
