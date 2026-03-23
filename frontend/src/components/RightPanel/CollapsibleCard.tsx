import type { ReactNode } from 'react';

interface CollapsibleCardProps {
  title: string;
  count: number;
  defaultOpen?: boolean;
  children: ReactNode;
}

// Wrapper around the native `details/summary` element to show/hide sections.
// If there is nothing to show (`count === 0`), we hide the card entirely.
const CollapsibleCard = ({ title, count, defaultOpen = false, children }: CollapsibleCardProps) => {
  if (count === 0) return null;

  return (
    <details className="collapsible-card" open={defaultOpen}>
      <summary className="collapsible-card-header">
        <span className="collapsible-card-title">{title}</span>
        <span className="collapsible-card-count">{count}</span>
      </summary>
      <div className="collapsible-card-body">
        {children}
      </div>
    </details>
  );
};

export default CollapsibleCard;
