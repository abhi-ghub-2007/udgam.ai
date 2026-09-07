/**
 * Market Decision Center -- the hero feature.
 *
 * A farmer arrives asking one question: "what should I do with this crop?"
 * So the page answers in that order:
 *
 *    1. BEST OPTION  -- one number, big, with who it's with
 *    2. WHY          -- the arithmetic, line by line, nothing hidden
 *    3. SELL OR WAIT -- risk-adjusted, never headline-price-chasing
 *    4. NEARBY MARKETS
 *
 * Everything shown here is computed by FastAPI (net_exit.py / sale_window.py).
 * No business logic lives in this component -- it renders a decision, it does
 * not make one.
 *
 * The three panels fetch independently: a market-data outage degrades one card
 * and leaves the rest usable, which matters on a rural connection.
 */
import { useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useMyListings, useNetExit, useSaleWindow, useMarketCompare } from '@/hooks/queries';
import { useAuth } from '@/services/auth/AuthProvider';
import {
  Card, CardSkeleton, CardTitle, EmptyState, ErrorState, Field,
  LinkButton, PageHeader, Select, cx,
} from '@/components/ui';
import { MethodBadge, ProvenanceStrip, RankedByNote } from '@/components/ui/Provenance';
import { ForecastCard } from '@/components/ForecastCard';
import { DemandForecastPanel } from '@/components/decisions/DemandForecastPanel';
import { money, number } from '@/utils/format';
import type { CostLine, Opportunity } from '@/types/api';

export default function Decisions() {
  const { t } = useTranslation();
  const { profile } = useAuth();
  const listings = useMyListings();

  const active = useMemo(
    () => (listings.data ?? []).filter((p) => p.status === 'active'),
    [listings.data],
  );
  const [selected, setSelected] = useState<string>('');
  const productId = selected || active[0]?.id;
  const lot = active.find((p) => p.id === productId);

  const netExit = useNetExit(productId);
  const saleWindow = useSaleWindow(productId);
  const markets = useMarketCompare(lot?.crop_id, lot?.district ?? profile?.district);

  if (listings.isLoading) {
    return <div className="space-y-4"><CardSkeleton /><CardSkeleton /></div>;
  }

  if (!active.length) {
    return (
      <div className="space-y-6">
        <PageHeader title={t('decide.title')} subtitle={t('decide.subtitle')} />
        <EmptyState
          title={t('decide.no_lots_title')}
          body={t('decide.no_lots_body')}
          action={<LinkButton to="/farmer/listings/new">{t('market.list_new')}</LinkButton>}
        />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <PageHeader title={t('decide.title')} subtitle={t('decide.subtitle')} />

      <Card className="max-w-md">
        <Field label={t('decide.choose_lot')} htmlFor="lot">
          <Select id="lot" value={productId ?? ''} onChange={(e) => setSelected(e.target.value)}>
            {active.map((p) => (
              <option key={p.id} value={p.id}>
                {/* Never fall back to crop_id: that puts a raw UUID in the
                    farmer's lot picker. An unnamed crop reads as "Produce". */}
                {p.crop_name ?? t('market.produce')} · {number(p.available_quantity_kg)} {t('common.kg')}
                {p.grade ? ` · ${t('product.grade')} ${p.grade}` : ''}
              </option>
            ))}
          </Select>
        </Field>
      </Card>

      {/* 1 + 2: the recommendation and the arithmetic behind it */}
      {netExit.isLoading ? <CardSkeleton lines={5} />
        : netExit.isError ? (
          <ErrorState
            title={t('decide.best_exit')} body={t('decide.unavailable')}
            retryLabel={t('common.retry')} onRetry={() => void netExit.refetch()}
          />
        ) : <BestExit data={netExit.data!} />}

      {/* 3: what the next week is likely to look like. Sits directly above
          sell-or-wait because it is the evidence that decision rests on, and
          the same forecast rows feed the Risk-Adjusted Sale Window below. */}
      <ForecastCard cropId={lot?.crop_id} district={lot?.district ?? profile?.district ?? undefined} />

      {/* 4: how much buyers are likely to want, over 3 / 15 / 30 days.
          Driven by the SAME `lot` the farmer already picked above -- there is
          deliberately no second crop selector, and net exit is passed in only
          so the decision context can phrase the trade-off. Demand never
          changes a net-realization number. */}
      <DemandForecastPanel
        cropId={lot?.crop_id}
        cropName={lot?.crop_name ?? undefined}
        district={lot?.district ?? profile?.district ?? undefined}
        netExit={netExit.data}
      />

      {/* 5: sell now or wait */}
      {saleWindow.isLoading ? <CardSkeleton lines={4} />
        : saleWindow.isError ? (
          <ErrorState
            title={t('decide.sell_or_wait')} body={t('decide.unavailable')}
            retryLabel={t('common.retry')} onRetry={() => void saleWindow.refetch()}
          />
        ) : <SaleWindow data={saleWindow.data!} />}

      {/* 4: nearby markets */}
      {markets.isLoading ? <CardSkeleton lines={4} />
        : markets.isError ? (
          <ErrorState
            title={t('decide.markets')} body={t('decide.unavailable')}
            retryLabel={t('common.retry')} onRetry={() => void markets.refetch()}
          />
        ) : <Markets data={markets.data!} />}
    </div>
  );
}

/* ----------------------------------------------------------- best exit --- */
function BestExit({ data }: { data: import('@/types/api').NetExitResponse }) {
  const { t } = useTranslation();
  const [open, setOpen] = useState(false);
  const best = data.best;

  if (data.availability !== 'ok' || !best) {
    return (
      <Card className="space-y-2">
        <CardTitle>{t('decide.best_exit')}</CardTitle>
        <p className="text-body text-ink-muted">{t('decide.no_exit')}</p>
      </Card>
    );
  }

  return (
    <Card className="space-y-5 animate-fade-up">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <CardTitle>{t('decide.best_exit')}</CardTitle>
        <MethodBadge method={data.method} />
      </div>

      {/* The answer, in the largest type on the page. */}
      <div className="rounded-lg bg-primary-container/50 px-5 py-5">
        <p className="text-label font-semibold uppercase tracking-[0.04em] text-primary-on-container">
          {best.reference_name} · {t(`decide.channel.${best.channel}`)}
        </p>
        <p className="tnum mt-1 text-display font-bold text-primary-on-container">
          {money(best.net_realization_paise)}
        </p>
        <p className="mt-1 text-body text-primary-on-container/80">{t('decide.expected_net')}</p>
      </div>

      <Breakdown lines={best.breakdown} total={best.net_realization_paise} />

      {best.reasons.length > 0 && (
        <ul className="space-y-1.5">
          {best.reasons.map((r, i) => (
            <li key={i} className="flex gap-2 text-body text-ink-muted">
              <span aria-hidden className="mt-2 h-1.5 w-1.5 shrink-0 rounded-full bg-primary" />
              {r}
            </li>
          ))}
        </ul>
      )}

      {best.limitations.length > 0 && (
        <ul className="space-y-1.5">
          {best.limitations.map((r, i) => (
            <li key={i} className="flex gap-2 text-body text-secondary-strong">
              <span aria-hidden className="mt-2 h-1.5 w-1.5 shrink-0 rounded-full bg-secondary" />
              {r}
            </li>
          ))}
        </ul>
      )}

      <ProvenanceStrip p={best.price_provenance} />

      {data.ranked.length > 1 && (
        <div>
          <button
            onClick={() => setOpen((v) => !v)}
            aria-expanded={open}
            className="min-h-tap font-semibold text-primary underline underline-offset-2"
          >
            {t('decide.compare_options', { n: data.ranked.length })}
          </button>
          {open && <Comparison ranked={data.ranked} rankedBy={data.ranked_by} />}
        </div>
      )}

      {data.excluded.length > 0 && <Excluded items={data.excluded} />}

      {data.neutrality && (
        <p className="border-t border-line-card pt-3 text-label text-ink-muted">
          {data.neutrality.statement}
        </p>
      )}
    </Card>
  );
}

/** The calculation, made visually obvious: what you get, what comes off. */
function Breakdown({ lines, total }: { lines: CostLine[]; total: number | null }) {
  const { t } = useTranslation();
  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[280px] border-collapse text-body">
        <caption className="sr-only">{t('decide.how_calculated')}</caption>
        <tbody>
          {lines.map((l, i) => {
            // "(paid by the buyer)" belongs only on a DEDUCTION that someone
            // other than the farmer bears -- it explains why that cost does not
            // reduce their take-home. On the gross line it would read as
            // nonsense ("Gross sale value (paid by the farmer)"), and dimming
            // the gross line would bury the largest number in the table.
            const borneByOther = l.kind === 'deduction' && !l.reduces_farmer_net;
            return (
            <tr key={i} className={cx('border-b border-line-card', borneByOther && 'opacity-60')}>
              <td className="py-2.5 pr-3">
                {l.label}
                {borneByOther && (
                  <span className="ml-1.5 text-label text-ink-muted">
                    ({t('decide.paid_by', { who: t(`decide.bearer.${l.borne_by}`) })})
                  </span>
                )}
              </td>
              <td className="tnum whitespace-nowrap py-2.5 text-right">
                {l.kind === 'gross' ? '' : '−'}{money(l.amount_paise)}
              </td>
            </tr>
            );
          })}
          <tr className="border-t-2 border-outline-variant font-bold">
            <td className="py-3 pr-3">{t('decide.expected_net')}</td>
            <td className="tnum whitespace-nowrap py-3 text-right text-primary">{money(total)}</td>
          </tr>
        </tbody>
      </table>
    </div>
  );
}

function Comparison({ ranked, rankedBy }: { ranked: Opportunity[]; rankedBy: string }) {
  const { t } = useTranslation();
  const max = Math.max(...ranked.map((o) => Math.abs(o.net_realization_paise ?? 0)), 1);
  return (
    <div className="mt-3 space-y-3">
      {ranked.map((o, i) => {
        const net = o.net_realization_paise ?? 0;
        const pct = Math.max(3, (Math.abs(net) / max) * 100);
        const negative = net < 0;
        return (
          <div key={o.reference_id ?? i} className="space-y-1">
            <div className="flex items-baseline justify-between gap-3">
              <span className="min-w-0 truncate text-body">
                {o.reference_name}
                <span className="ml-1.5 text-label text-ink-muted">
                  {t(`decide.channel.${o.channel}`)}
                  {o.distance_km != null && ` · ${number(Math.round(o.distance_km))} km`}
                </span>
              </span>
              <span className={cx('tnum shrink-0 font-semibold', negative ? 'text-danger' : i === 0 ? 'text-primary' : 'text-ink')}>
                {money(net)}
              </span>
            </div>
            <div className="h-1.5 overflow-hidden rounded-full bg-surface-high">
              <div
                className={cx('h-full origin-left rounded-full animate-draw-line',
                  negative ? 'bg-danger' : i === 0 ? 'bg-primary' : 'bg-outline-variant')}
                style={{ width: `${pct}%` }}
              />
            </div>
          </div>
        );
      })}
      <RankedByNote rankedBy={rankedBy} />
    </div>
  );
}

/** Options the engine could not cost. Shown, with the reason -- never hidden. */
function Excluded({ items }: { items: Opportunity[] }) {
  const { t } = useTranslation();
  const [open, setOpen] = useState(false);
  return (
    <div>
      <button onClick={() => setOpen((v) => !v)} aria-expanded={open}
              className="min-h-tap font-semibold text-primary underline underline-offset-2">
        {t('decide.excluded_options', { n: items.length })}
      </button>
      {open && (
        <ul className="mt-2 space-y-1.5">
          {items.map((o, i) => (
            <li key={i} className="text-body text-ink-muted">
              <span className="font-medium text-ink">{o.reference_name}</span>
              {': '}{o.blockers[0] ?? o.limitations[0] ?? ''}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

/* --------------------------------------------------------- sale window --- */
function SaleWindow({ data }: { data: import('@/types/api').SaleWindowResponse }) {
  const { t } = useTranslation();
  if (data.availability !== 'ok' || !data.scenarios.length) {
    return (
      <Card className="space-y-2">
        <CardTitle>{t('decide.sell_or_wait')}</CardTitle>
        <p className="text-body text-ink-muted">{t('decide.no_window')}</p>
      </Card>
    );
  }
  const sellNow = data.recommendation === 'sell_now';
  return (
    <Card className="space-y-5 animate-fade-up">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <CardTitle>{t('decide.sell_or_wait')}</CardTitle>
        <MethodBadge method={data.method} />
      </div>

      <p className={cx('text-stat font-bold', sellNow ? 'text-primary' : 'text-secondary-strong')}>
        {t(sellNow ? 'decide.verdict_sell_now' : 'decide.verdict_wait')}
      </p>

      <div className="overflow-x-auto">
        <table className="w-full min-w-[420px] border-collapse text-body">
          <thead>
            <tr className="border-b border-outline-variant text-label uppercase tracking-[0.04em] text-ink-muted">
              <th className="py-2 text-left font-semibold">{t('decide.scenario')}</th>
              <th className="py-2 text-right font-semibold">{t('decide.net')}</th>
              <th className="py-2 text-right font-semibold">{t('decide.risk_charge')}</th>
              <th className="py-2 text-right font-semibold">{t('decide.risk_adjusted')}</th>
            </tr>
          </thead>
          <tbody>
            {data.scenarios.map((s, i) => {
              const isBest = s.reference_id === data.best?.reference_id;
              return (
                <tr key={i} className={cx('border-b border-line-card', isBest && 'font-bold')}>
                  <td className="py-2.5 pr-3">
                    {s.reference_name}
                    {s.storage_cost_paise > 0 && (
                      <span className="block text-label font-normal text-ink-muted">
                        {t('decide.storage')}: {money(s.storage_cost_paise)}
                      </span>
                    )}
                  </td>
                  <td className="tnum whitespace-nowrap py-2.5 text-right">{money(s.net_realization_paise)}</td>
                  <td className="tnum whitespace-nowrap py-2.5 text-right text-ink-muted">
                    {s.risk_penalty_paise ? `−${money(s.risk_penalty_paise)}` : '—'}
                  </td>
                  <td className={cx('tnum whitespace-nowrap py-2.5 text-right', isBest && 'text-primary')}>
                    {money(s.risk_adjusted_paise)}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      {data.best?.risk_notes && data.best.risk_notes.length > 0 && (
        <ul className="space-y-1">
          {data.best.risk_notes.map((n, i) => (
            <li key={i} className="text-body text-ink-muted">{n}</li>
          ))}
        </ul>
      )}

      {data.excluded.length > 0 && (
        <ul className="space-y-1">
          {data.excluded.map((s, i) => (
            <li key={i} className="text-body text-secondary-strong">
              <span className="font-medium">{s.reference_name}</span>
              {': '}{s.blockers[0] ?? s.limitations[0] ?? ''}
            </li>
          ))}
        </ul>
      )}

      <p className="border-t border-line-card pt-3 text-label text-ink-muted">
        {t('decide.risk_explainer')}
      </p>
    </Card>
  );
}

/* ------------------------------------------------------------- markets --- */
function Markets({ data }: { data: import('@/types/api').MarketCompare }) {
  const { t } = useTranslation();
  if (data.availability !== 'ok' || !data.markets.length) {
    return (
      <Card className="space-y-2">
        <CardTitle>{t('decide.markets')}</CardTitle>
        <p className="text-body text-ink-muted">{t('decide.no_markets')}</p>
      </Card>
    );
  }
  const arrow = (d: string) => (d === 'rising' ? '↑' : d === 'falling' ? '↓' : '→');
  return (
    <Card className="space-y-4 animate-fade-up">
      <CardTitle>{t('decide.markets')}</CardTitle>
      <div className="overflow-x-auto">
        <table className="w-full min-w-[380px] border-collapse text-body">
          <thead>
            <tr className="border-b border-outline-variant text-label uppercase tracking-[0.04em] text-ink-muted">
              <th className="py-2 text-left font-semibold">{t('decide.market')}</th>
              <th className="py-2 text-right font-semibold">{t('decide.price_per_kg')}</th>
              <th className="py-2 text-right font-semibold">{t('decide.trend')}</th>
              <th className="py-2 text-right font-semibold">{t('decide.distance')}</th>
            </tr>
          </thead>
          <tbody>
            {data.markets.map((m) => (
              <tr key={m.district} className="border-b border-line-card">
                <td className="py-2.5 pr-3">{m.district}</td>
                <td className="tnum whitespace-nowrap py-2.5 text-right">{money(m.modal_price_paise)}</td>
                <td className="tnum whitespace-nowrap py-2.5 text-right text-ink-muted">
                  {arrow(m.trend.direction)} {m.trend.change_pct != null ? `${m.trend.change_pct}%` : ''}
                </td>
                <td className="tnum whitespace-nowrap py-2.5 text-right text-ink-muted">
                  {m.distance_km != null ? `${number(Math.round(m.distance_km))} km` : '—'}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <ProvenanceStrip p={data.markets[0]?.provenance} explain />
      <RankedByNote rankedBy={data.ranked_by} />
    </Card>
  );
}
