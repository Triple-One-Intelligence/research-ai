/** rightPanelUtils.ts - utility functions for the right panel. Most of them are for filtering options. */

import type { Publication } from '../../types';

/** Publication sort modes supported by the right-panel toolbar. */
export type PublicationsSort = 'year_desc' | 'year_asc' | 'title_asc' | 'title_desc';

/** Name sort for collaborators, members, and organizations. */
export type NameSort = 'name_asc' | 'name_desc';

/** Trim and lowercase for case-insensitive matching. */
export function normalizeFilterText(s: string): string {
  return s.trim().toLowerCase();
}

/** True if `needle` is empty or `haystack` contains `needle` (case-insensitive). */
export function matchesText(haystack: string | undefined, needle: string): boolean {
  if (!needle) return true;
  if (!haystack) return false;
  return haystack.toLowerCase().includes(needle);
}

/** Parse year from input; empty string means no bound. */
export function parseYearInput(raw: string): number | undefined {
  const t = raw.trim();
  if (!t) return undefined;
  const n = Number.parseInt(t, 10);
  return Number.isFinite(n) ? n : undefined;
}

/** Only apply publication year filtering once the input looks like a complete year. */
export function parsePublicationFilterYearInput(raw: string): number | undefined {
  const t = raw.trim();
  if (!t) return undefined;
  if (!/^\d{4,}$/.test(t)) return undefined;
  return parseYearInput(t);
}

/** Clamp a single publication year input to [0, maxYear], while still allowing an empty field. */
export function clampPublicationYearInput(raw: string, maxYear: number): string {
  if (raw.trim() === '') return '';
  const parsed = parseYearInput(raw);
  if (parsed == null) return raw;
  return String(Math.min(Math.max(parsed, 0), maxYear));
}

/** Whether `pub.year` lies in the effective year range when bounds are set. */
export function publicationInYearRange(
  pub: Publication,
  yearFrom: number | undefined,
  yearTo: number | undefined,
  includeUnknownYear: boolean,
): boolean {
  const y = pub.year;
  if (y == null) return includeUnknownYear;
  if (yearFrom != null && y < yearFrom) return false;
  if (yearTo != null && y > yearTo) return false;
  return true;
}

/**
 * Filter publications by optional text (title, DOI, category substring) and year range.
 */
export function filterPublications(
  pubs: Publication[],
  filterText: string,
  yearFrom: number | undefined,
  yearTo: number | undefined,
  includeUnknownYear: boolean,
): Publication[] {
  const n = normalizeFilterText(filterText);
  return pubs.filter((pub) => {
    if (!publicationInYearRange(pub, yearFrom, yearTo, includeUnknownYear)) return false;
    if (!n) return true;
    return matchesText(pub.title, n) || matchesText(pub.doi, n) || matchesText(pub.category, n);
  });
}

/** Sort publications by year or title (stable tie-breakers where useful). */
export function sortPublications(pubs: Publication[], sort: PublicationsSort): Publication[] {
  const out = [...pubs];
  const titleKey = (p: Publication) => (p.title ?? p.doi ?? '').toLowerCase();
  const yearKey = (p: Publication, fallback: number) => p.year ?? fallback;

  switch (sort) {
    case 'year_desc':
      out.sort(
        (a, b) =>
          yearKey(b, -Infinity) - yearKey(a, -Infinity) || titleKey(a).localeCompare(titleKey(b)),
      );
      break;
    case 'year_asc':
      out.sort(
        (a, b) =>
          yearKey(a, Infinity) - yearKey(b, Infinity) || titleKey(a).localeCompare(titleKey(b)),
      );
      break;
    case 'title_asc':
      out.sort((a, b) => titleKey(a).localeCompare(titleKey(b)));
      break;
    case 'title_desc':
      out.sort((a, b) => titleKey(b).localeCompare(titleKey(a)));
      break;
    default:
      break;
  }
  return out;
}

/** Sort items with a `name` field A-Z or Z-A. */
export function sortByName<T extends { name: string }>(items: T[], sort: NameSort): T[] {
  const out = [...items];
  out.sort((a, b) =>
    sort === 'name_asc'
      ? a.name.localeCompare(b.name, undefined, { sensitivity: 'base' })
      : b.name.localeCompare(a.name, undefined, { sensitivity: 'base' }),
  );
  return out;
}
