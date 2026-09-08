/**
 * Formatting helpers. Ported from the legacy core/i18n.js so number/currency
 * output is identical to before (en-IN grouping: 9,360 not 9,360.00).
 *
 * All money in this system is INTEGER PAISE end to end -- the backend never
 * sends rupees, and these helpers are the only place the /100 happens.
 */
export function money(paise: number | null | undefined, opts?: { compact?: boolean }): string {
  const rupees = (paise ?? 0) / 100;
  return new Intl.NumberFormat('en-IN', {
    style: 'currency',
    currency: 'INR',
    maximumFractionDigits: rupees % 1 === 0 ? 0 : 2,
    notation: opts?.compact ? 'compact' : 'standard',
  }).format(rupees);
}

export function number(n: number | null | undefined): string {
  return new Intl.NumberFormat('en-IN').format(n ?? 0);
}

export function date(iso: string | null | undefined): string {
  if (!iso) return '';
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return '';
  return new Intl.DateTimeFormat('en-IN', { day: 'numeric', month: 'short', year: 'numeric' }).format(d);
}

/** Date AND time. A case timeline needs the clock: "acknowledged 10:44,
    resolved 12:30" is the thing that makes it an audit trail rather than a
    list of days. */
export function dateTime(iso: string | null | undefined): string {
  if (!iso) return '';
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return '';
  return new Intl.DateTimeFormat('en-IN', {
    day: 'numeric', month: 'short', hour: 'numeric', minute: '2-digit',
  }).format(d);
}

export function relativeDays(iso: string | null | undefined): number | null {
  if (!iso) return null;
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return null;
  return Math.round((d.getTime() - Date.now()) / 86_400_000);
}
