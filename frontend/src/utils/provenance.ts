/**
 * Presentation mapping for machine-readable API metadata.
 *
 * The backend deliberately returns identifiers a program can reason about --
 * `data_source: "synthetic_v1"`, `ranked_by: "modal_price_paise desc"`. That
 * is correct for an API and stays exactly as it is. What was wrong is that the
 * UI printed those identifiers straight onto a farmer's screen.
 *
 * This module is the seam: machine id in, i18n key out. Nothing here invents
 * meaning -- every mapping states what the backend value actually is, and an
 * unrecognised value degrades to "not shown" rather than to a guess, because a
 * wrong provenance label is worse than no provenance label.
 */

/** Sort fields the backend can name, mapped to what they mean to a farmer.
 *
 *  Keys are the real field names: the nine declared in
 *  backend/app/services/orchestration.py RANKING_FACTORS, plus the two that
 *  routers name directly (`modal_price_paise` in market.py, and
 *  `estimated_cost_paise` in transport.py). */
const RANK_FIELD_KEYS: Record<string, string> = {
  modal_price_paise: 'rank.modal_price',
  expected_farmer_net_realization_paise: 'rank.net_realization',
  risk_adjusted_paise: 'rank.risk_adjusted',
  unit_price_paise: 'rank.unit_price',
  estimated_cost_paise: 'rank.estimated_cost',
  distance_km: 'rank.distance',
  quantity_fit: 'rank.quantity_fit',
  quality_fit: 'rank.quality_fit',
  deadline_fit: 'rank.deadline_fit',
  payment_reliability: 'rank.payment_reliability',
  reference_id: 'rank.reference_id',
};

/** Data sources, mapped to an honest description of what they actually are.
 *
 *  `agmarknet` (bare) is the `prices.data_source` column DEFAULT, not a real
 *  integration -- backend/app/services/market_data.py says so explicitly. A row
 *  carrying it has an unstated origin, so it is labelled as unverified rather
 *  than as government data. Calling it "Agmarknet" here would launder a column
 *  default into a provenance claim. */
const SOURCE_KEYS: Record<string, string> = {
  synthetic_v1: 'provenance.source_simulated',
  agmarknet: 'provenance.source_unspecified',
};

/** Sources are versioned by ingest date (`agmarknet_csv_20251107_20260906`),
 *  so real feeds are matched by prefix rather than listed one by one. */
const SOURCE_PREFIX_KEYS: [string, string][] = [
  ['agmarknet_csv', 'provenance.source_agmarknet_csv'],
];

export interface RankFactor {
  /** i18n key describing the field, e.g. 'rank.modal_price'. */
  key: string;
  /** True when higher is first. */
  descending: boolean;
}

/**
 * Parse a backend `ranked_by` string into its factors, primary first.
 *
 * Accepts both shapes the backend produces:
 *   "modal_price_paise desc"
 *   "estimated_cost_paise asc, then distance_km asc, then reference_id asc"
 *
 * Unknown fields are dropped rather than displayed raw -- that is the whole
 * point of this function, and it means adding a new ranking factor server-side
 * can never leak a column name into the UI before its label exists.
 */
export function parseRankedBy(rankedBy: string | null | undefined): RankFactor[] {
  if (!rankedBy) return [];
  return rankedBy
    .split(/,\s*then\s*|,\s*/)
    .map((part) => {
      const [field, dir] = part.trim().split(/\s+/);
      const key = RANK_FIELD_KEYS[field];
      return key ? { key, descending: dir !== 'asc' } : null;
    })
    .filter((f): f is RankFactor => f !== null);
}

/**
 * The single factor worth showing a farmer: the primary sort.
 *
 * Tie-breakers are real and are still returned by the API for anyone auditing
 * neutrality, but "then reference_id asc" is noise on a farmer's screen and
 * printing the full chain is how the raw string looked like debug output in
 * the first place.
 */
export function primaryRankFactor(rankedBy: string | null | undefined): RankFactor | null {
  return parseRankedBy(rankedBy)[0] ?? null;
}

/** i18n key describing a data source, or null when it should not be shown. */
export function sourceLabelKey(source: string | null | undefined): string | null {
  if (!source) return null;
  const exact = SOURCE_KEYS[source];
  if (exact) return exact;
  const prefixed = SOURCE_PREFIX_KEYS.find(([p]) => source.startsWith(p));
  if (prefixed) return prefixed[1];
  // An identifier nobody has written a label for. Showing it raw is the bug
  // this module exists to prevent, so it is withheld instead.
  return null;
}
