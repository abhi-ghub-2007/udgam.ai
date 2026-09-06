/**
 * Farmer dashboard. Answers "what should I do today?" before "here are your
 * metrics" -- the top opportunity comes before the stat tiles in reading
 * order on mobile, because that is the reason a farmer opens the app.
 *
 * The dashboard payload and the matching feed are independent requests and
 * resolve independently, so a slow matching feed never blocks the numbers.
 */
import { useTranslation } from 'react-i18next';
import { useFarmerDashboard, useMatchingBuyers } from '@/hooks/queries';
import { useAuth } from '@/services/auth/AuthProvider';
import {
  Badge, Card, CardTitle, EmptyState, ErrorState, LinkButton, PageHeader,
  StatCard, StatSkeleton, CardSkeleton,
} from '@/components/ui';
import { money, number } from '@/utils/format';
import { ProductCard } from '@/components/ProductCard';

export default function FarmerHome() {
  const { t } = useTranslation();
  const { profile } = useAuth();
  const dash = useFarmerDashboard();
  const matches = useMatchingBuyers();

  const listings = dash.data?.listings ?? [];
  const totalKg = listings.reduce((s, p) => s + (p.available_quantity_kg || 0), 0);
  const expected = listings.reduce(
    (s, p) => s + (p.available_quantity_kg || 0) * (p.asking_price_paise || 0), 0,
  );
  const best = matches.data?.[0];

  return (
    <div className="space-y-6">
      <PageHeader
        title={t('farmer.dashboard.greeting', { name: profile?.full_name ?? '' })}
        subtitle={t('farmer.dashboard.subtitle')}
        actions={
          <>
            <LinkButton to="/farmer/listings/new">{t('market.list_new')}</LinkButton>
            <LinkButton to="/farmer/decisions" variant="outline">{t('decide.title')}</LinkButton>
          </>
        }
      />

      {/* The opportunity, before the metrics. */}
      {matches.isLoading ? <CardSkeleton lines={2} /> : best && (
        <Card className="space-y-3 border-primary/25 bg-primary-container/25 animate-fade-up">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <span className="text-label font-semibold uppercase tracking-[0.04em] text-primary-on-container">
              {t('market.selling_opportunity')}
            </span>
            <Badge tone="insight">{t('ai.method_ALGORITHMIC')}</Badge>
          </div>
          <h2 className="text-h2 font-semibold text-ink">
            {best.crop_name} · {number(best.quantity_kg)} {t('common.kg')}
            {best.delivery_district ? ` → ${best.delivery_district}` : ''}
          </h2>
          {best.target_price_paise != null && (
            <p className="tnum text-stat font-bold text-primary">
              {money(Math.round(best.quantity_kg * best.target_price_paise))}
            </p>
          )}
          {best.reasons?.length > 0 && (
            <ul className="space-y-1">
              {best.reasons.slice(0, 3).map((r, i) => (
                <li key={i} className="text-body text-ink-muted">{r}</li>
              ))}
            </ul>
          )}
          <LinkButton to="/farmer/buyers">{t('market.review_offer')}</LinkButton>
        </Card>
      )}

      <section className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {dash.isLoading ? (
          Array.from({ length: 4 }).map((_, i) => <StatSkeleton key={i} />)
        ) : (
          <>
            <StatCard label={t('farmer.dashboard.active_listings')}
                      value={String(dash.data?.active_listings ?? 0)}
                      note={`${number(totalKg)} ${t('common.kg')}`} />
            <StatCard label={t('farmer.dashboard.earnings_expected')}
                      value={money(expected, { compact: true })}
                      note={t('market.at_asking_price')} tone="secondary" />
            <StatCard label={t('farmer.dashboard.open_requests_count')}
                      value={String(dash.data?.open_requests?.length ?? 0)}
                      note={t('market.for_your_crops')} tone="primary" />
            <StatCard label={t('farmer.dashboard.active_orders')}
                      value={String(dash.data?.active_orders ?? 0)} />
          </>
        )}
      </section>

      <section className="space-y-3">
        <div className="flex items-center justify-between gap-3">
          <CardTitle>{t('farmer.dashboard.active_listings')}</CardTitle>
          <LinkButton to="/farmer/listings" variant="ghost" size="sm">
            {t('market.view_all')} →
          </LinkButton>
        </div>

        {dash.isLoading ? <CardSkeleton />
          : dash.isError ? (
            <ErrorState title={t('common.error_title')} body={t('common.error_body')}
                        retryLabel={t('common.retry')} onRetry={() => void dash.refetch()} />
          ) : listings.length === 0 ? (
            <EmptyState
              title={t('market.empty_listings')}
              action={<LinkButton to="/farmer/listings/new">{t('market.list_new')}</LinkButton>}
            />
          ) : (
            <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
              {listings.slice(0, 6).map((p) => (
                <ProductCard key={p.id} product={p} to={`/farmer/listings/${p.id}`} />
              ))}
            </div>
          )}
      </section>
    </div>
  );
}
