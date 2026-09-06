/**
 * Honesty labelling. THE core UDGAM UX principle (master prompt 17).
 *
 * Every market figure carries where it came from and how much to trust it.
 * Simulated data must never be able to look observed, and an estimate must
 * never look like a measurement. The backend already computes this
 * (services/market_data.py); this component's only job is to render it
 * faithfully and never soften it.
 */
import { useTranslation } from 'react-i18next';
import { Badge } from './index';
import type { Freshness, MethodLabel, Provenance as ProvenanceT } from '@/types/api';

const FRESHNESS_TONE: Record<Freshness, 'success' | 'info' | 'warning' | 'danger'> = {
  LIVE: 'success',
  RECENT: 'info',
  ESTIMATED: 'warning',
  SYNTHETIC: 'warning',
  STALE: 'danger',
};

export function MethodBadge({ method }: { method: MethodLabel | null | undefined }) {
  const { t } = useTranslation();
  if (!method) return null;
  // ALGORITHMIC/HEURISTIC output uses the reserved insight colour; REAL and
  // SYNTHETIC are data provenance, not model output.
  const tone = method === 'ALGORITHMIC' || method === 'HEURISTIC' ? 'insight' : 'neutral';
  return <Badge tone={tone}>{t(`ai.method_${method}`)}</Badge>;
}

export function FreshnessBadge({ freshness }: { freshness: Freshness | null | undefined }) {
  const { t } = useTranslation();
  if (!freshness) return null;
  return <Badge tone={FRESHNESS_TONE[freshness]}>{t(`decide.freshness.${freshness}`)}</Badge>;
}

/** The full provenance strip: freshness, method, source, confidence. */
export function ProvenanceStrip({ p }: { p: ProvenanceT | null | undefined }) {
  const { t } = useTranslation();
  if (!p) return null;
  return (
    <div className="flex flex-wrap items-center gap-2">
      <FreshnessBadge freshness={p.freshness} />
      <MethodBadge method={p.method} />
      {p.source && (
        <span className="text-label text-ink-muted">
          {t('decide.source')}: {p.source}
        </span>
      )}
      {p.confidence != null && (
        <span className="text-label text-ink-muted">
          {t('decide.confidence')}: {Math.round(p.confidence * 100)}%
        </span>
      )}
    </div>
  );
}
