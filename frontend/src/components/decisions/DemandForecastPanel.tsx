/**
 * Demand Forecast, inside the Market Decision Center.
 *
 * NOT a separate page and NOT a second crop picker: it receives the crop the
 * farmer already chose for Net Realization, so one selection drives both
 * halves of the decision (rules 3, 4, 34).
 *
 * The farmer's question is "how much will buyers want, and should that change
 * what I do today?" -- so the panel answers in that order: the quantity, the
 * direction, the shape, then what it means next to the net-realization figure
 * already on screen. The horizon selector sits at the top because it is the
 * one control here, and its three options are the whole feature.
 *
 * HONESTY IS PART OF THE LAYOUT, NOT A FOOTNOTE
 * ----------------------------------------------
 * Three outcomes are possible and each looks different on purpose:
 *   REAL              a badge, and nothing apologetic
 *   SYNTHETIC         a badge plus the sentence saying it is a demonstration,
 *                     shown ABOVE the number rather than under the chart
 *   INSUFFICIENT_DATA no number at all -- the counts that fell short instead
 * A simulated figure must never be able to read as a measurement, so the
 * disclaimer is placed where it cannot be scrolled past.
 */
import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useDemandHorizon } from '@/hooks/queries';
import { Badge, Card, CardSkeleton, CardTitle, cx } from '@/components/ui';
import { MethodBadge } from '@/components/ui/Provenance';
import { DemandChart } from '@/components/charts/DemandChart';
import { number } from '@/utils/format';
import type { ForecastHorizon, NetExitResponse } from '@/types/api';

const HORIZONS: ForecastHorizon[] = ['3_days', '15_days', '30_days'];

const TREND_TONE = {
  INCREASING: 'success', DECREASING: 'warning', STABLE: 'neutral',
} as const;

// Direction is spelled out as well as arrowed, so it never depends on colour.
const TREND_ARROW = { INCREASING: '↑', DECREASING: '↓', STABLE: '→' } as const;

const RELIABILITY_TONE = {
  HIGH: 'success', MODERATE: 'neutral', LOW: 'warning',
} as const;

export function DemandForecastPanel({ cropId, cropName, district, netExit }: {
  cropId: string | undefined;
  cropName: string | undefined;
  district: string | undefined;
  /** Used only to phrase the combined decision context. The demand forecast
      never alters a net-realization number. */
  netExit?: NetExitResponse;
}) {
  const { t } = useTranslation();
  const [horizon, setHorizon] = useState<ForecastHorizon>('15_days');
  const q = useDemandHorizon(cropId, horizon, district);

  if (!cropId) {
    return (
      <Card className="space-y-2">
        <CardTitle>{t('demand.title')}</CardTitle>
        <p className="text-body text-ink-muted">{t('demand.select_produce')}</p>
      </Card>
    );
  }

  const d = q.data;

  return (
    <Card className="space-y-4 animate-fade-up">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <CardTitle>{t('demand.title')}</CardTitle>
          <p className="text-label text-ink-muted">{t('demand.subtitle')}</p>
        </div>
        {d?.available && <MethodBadge method={d.data_status === 'REAL' ? 'REAL' : 'SYNTHETIC'} />}
      </div>

      {/* Horizon selector. A radiogroup rather than buttons so arrow keys work
          and the current choice is announced. Wraps to one-per-row on a phone. */}
      <div role="radiogroup" aria-label={t('demand.horizon_label')} className="flex flex-wrap gap-2">
        {HORIZONS.map((h) => {
          const active = h === horizon;
          return (
            <button
              key={h}
              role="radio"
              aria-checked={active}
              onClick={() => setHorizon(h)}
              className={cx(
                'min-h-tap flex-1 rounded-md border px-4 py-2.5 text-body font-semibold transition-colors sm:flex-none',
                active
                  ? 'border-primary bg-primary text-primary-on'
                  : 'border-outline-variant bg-surface text-ink hover:bg-surface-low',
              )}
            >
              {t(`demand.horizon_${h}`)}
            </button>
          );
        })}
      </div>

      {q.isLoading && (
        <div className="space-y-2">
          <p className="text-label text-ink-muted">{t('demand.analyzing')}</p>
          <CardSkeleton lines={3} />
        </div>
      )}

      {q.isError && (
        <p role="alert" className="rounded-md bg-danger-container px-3 py-2 text-body text-danger-on-container">
          {t('demand.error')}
        </p>
      )}

      {d && !d.available && (
        /* An honest refusal, visually distinct from an API failure. It reports
           what exists rather than only what is missing, so the farmer can see
           the feature is waiting on data rather than broken. */
        <div className="space-y-2 rounded-md bg-surface-low px-3 py-3">
          <p className="text-body font-semibold">{t('demand.insufficient_title')}</p>
          <p className="text-body text-ink-muted">
            {t('demand.insufficient_body', { crop: cropName ?? d.crop ?? '' })}
          </p>
          <p className="text-label text-ink-muted">
            {t('demand.insufficient_counts', {
              days: d.history_days, events: d.demand_events,
              needDays: d.required_history_days ?? 0, needEvents: d.required_events ?? 0,
            })}
          </p>
        </div>
      )}

      {d?.available && (
        <>
          {/* Placed above the figure on purpose: a demonstration number must
              be labelled before it is read, not after. */}
          {!d.is_real && d.disclaimer && (
            <p className="rounded-md bg-secondary-container px-3 py-2 text-label text-secondary-on-container">
              {t('demand.simulated_note')}
            </p>
          )}

          <div className="flex flex-wrap items-end justify-between gap-3">
            <div>
              <p className="text-label text-ink-muted">{t('demand.expected')}</p>
              <p className="tnum text-h1 font-bold text-primary">
                {number(Math.round(d.total_expected_demand_kg ?? 0))} {t('common.kg')}
              </p>
              <p className="text-label text-ink-muted">{t(`demand.horizon_${d.horizon}`)}</p>
            </div>
            {d.trend && (
              <div className="text-right">
                <Badge tone={TREND_TONE[d.trend]}>
                  {TREND_ARROW[d.trend]} {t(`demand.trend_${d.trend}`)}
                </Badge>
                {d.reliability && (
                  <p className="mt-1.5 text-label text-ink-muted">
                    {t('demand.reliability')}:{' '}
                    <span className={cx(
                      RELIABILITY_TONE[d.reliability] === 'warning' && 'text-secondary-strong',
                    )}>
                      {t(`demand.reliability_${d.reliability}`)}
                    </span>
                  </p>
                )}
              </div>
            )}
          </div>

          <DemandChart
            points={d.forecast}
            bucketed={d.horizon !== '3_days'}
            ariaSummary={t('demand.chart_summary', {
              kg: number(Math.round(d.total_expected_demand_kg ?? 0)),
              period: t(`demand.horizon_${d.horizon}`),
              trend: t(`demand.trend_${d.trend ?? 'STABLE'}`),
            })}
          />

          {/* Interpretation, not instruction. */}
          <p className="text-body text-ink-muted">{t(`demand.insight_${d.insight}`)}</p>

          <DecisionContext demand={d} netExit={netExit} />

          <details className="text-label text-ink-muted">
            <summary className="min-h-tap cursor-pointer select-none py-1">
              {t('demand.why')}
            </summary>
            <ul className="mt-2 space-y-1">
              {(d.factors ?? []).map((f) => (
                <li key={f}>• {t(`demand.factor_${f}`, { defaultValue: f })}</li>
              ))}
              <li>• {t('demand.factor_observations', {
                days: d.history_days, events: d.demand_events,
              })}</li>
            </ul>
          </details>
        </>
      )}
    </Card>
  );
}

/** The reason this feature sits inside the Decision Center rather than beside it.
 *
 *  Demand alone does not answer "sell now or wait" -- waiting costs storage,
 *  spoilage and certainty, which the Risk-Adjusted Sale Window already prices.
 *  So this states both facts and hands the trade-off back, and deliberately
 *  stops short of saying WAIT: only the sale-window engine has the arithmetic
 *  to support that, and contradicting it here would be worse than saying
 *  nothing (rules 18, 19). */
function DecisionContext({ demand, netExit }: {
  demand: NonNullable<ReturnType<typeof useDemandHorizon>['data']>;
  netExit?: NetExitResponse;
}) {
  const { t } = useTranslation();
  const best = netExit?.best;
  if (!demand.trend) return null;

  return (
    <div className="space-y-1.5 rounded-md border border-line-card px-3 py-3">
      <p className="text-label font-semibold uppercase tracking-[0.04em] text-ink-muted">
        {t('demand.decision_context')}
      </p>
      {best && netExit?.availability === 'ok' ? (
        <p className="text-body">
          {t(`demand.context_${demand.trend}`)}
        </p>
      ) : (
        <p className="text-body text-ink-muted">{t('demand.context_no_net_exit')}</p>
      )}
      {!demand.is_real && (
        <p className="text-label text-ink-muted">{t('demand.context_simulated_caveat')}</p>
      )}
    </div>
  );
}
