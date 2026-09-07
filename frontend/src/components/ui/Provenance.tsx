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
import { primaryRankFactor, sourceLabelKey } from '@/utils/provenance';
import type { Freshness, MethodLabel, Provenance as ProvenanceT } from '@/types/api';

const FRESHNESS_TONE: Record<Freshness, 'success' | 'info' | 'warning' | 'danger'> = {
  LIVE: 'success',
  RECENT: 'info',
  ESTIMATED: 'warning',
  SYNTHETIC: 'warning',
  STALE: 'danger',
};

/** 'MIXED' is not a stored method label -- it is what a deployment looks like
 *  when its `prices` table holds both observed and seeded rows. It is accepted
 *  here so that state can be shown honestly instead of rounded to REAL. */
export function MethodBadge({ method }: { method: MethodLabel | 'MIXED' | null | undefined }) {
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

/** The full provenance strip: freshness, method, source, confidence.
 *
 * Two rules this component now enforces, both of which it previously broke:
 *
 * 1. SAY IT ONCE. `freshness: 'SYNTHETIC'` renders "Simulated" and
 *    `method: 'SYNTHETIC'` renders "Sample data" -- the same fact, twice,
 *    side by side. Simulated market data was showing three near-identical
 *    labels in a row. When both say synthetic, one badge is shown.
 *
 * 2. NEVER PRINT AN INTERNAL IDENTIFIER. `p.source` is a machine id
 *    (`synthetic_v1`), and it was being printed verbatim after "Source:".
 *    It now goes through the presentation mapping, which withholds anything
 *    it cannot describe honestly rather than falling back to the raw value.
 *
 * Neither rule removes information: what the data IS remains on screen, in
 * words a farmer can read.
 */
export function ProvenanceStrip({ p, explain = false }: {
  p: ProvenanceT | null | undefined;
  /** Add the one-line plain explanation under the badges. Opt-in, so a page
      showing several strips states the caveat once instead of shouting it. */
  explain?: boolean;
}) {
  const { t } = useTranslation();
  if (!p) return null;

  const isSimulated = p.freshness === 'SYNTHETIC' || p.method === 'SYNTHETIC';
  const bothSaySynthetic = p.freshness === 'SYNTHETIC' && p.method === 'SYNTHETIC';
  const sourceKey = sourceLabelKey(p.source);

  return (
    <div className="space-y-1.5">
      <div className="flex flex-wrap items-center gap-x-3 gap-y-1.5">
        <FreshnessBadge freshness={p.freshness} />
        {/* Suppressed only when it would repeat the freshness badge verbatim. */}
        {!bothSaySynthetic && <MethodBadge method={p.method} />}
        {sourceKey && (
          <span className="text-label text-ink-muted">
            {t('decide.source')}: {t(sourceKey)}
          </span>
        )}
        {p.confidence != null && (
          <span className="text-label text-ink-muted">
            {t('decide.confidence')}: {Math.round(p.confidence * 100)}%
          </span>
        )}
      </div>
      {explain && isSimulated && (
        <p className="text-label text-ink-muted">{t('provenance.simulated_note')}</p>
      )}
    </div>
  );
}

/** "Sorted by: highest market price" -- the primary ranking factor, in words.
 *
 * Replaces printing the backend's raw sort expression
 * ("modal_price_paise desc"). The API keeps returning that string; this is
 * simply the only thing allowed to render it. */
export function RankedByNote({ rankedBy }: { rankedBy: string | null | undefined }) {
  const { t } = useTranslation();
  const factor = primaryRankFactor(rankedBy);
  if (!factor) return null;
  return (
    <p className="text-label text-ink-muted">
      {t('decide.ranked_by')}: {t(factor.descending ? 'rank.highest_first' : 'rank.lowest_first',
        { factor: t(factor.key) })}
    </p>
  );
}
