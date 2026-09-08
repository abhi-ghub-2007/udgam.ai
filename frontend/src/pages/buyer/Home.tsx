import { useTranslation } from 'react-i18next';
import { useBuyerDashboard } from '@/hooks/queries';
import { useAuth } from '@/services/auth/AuthProvider';
import {
  Badge, Card, CardSkeleton, CardTitle, EmptyState, ErrorState, LinkButton,
  PageHeader, StatCard, StatSkeleton,
} from '@/components/ui';
import { ProductCard } from '@/components/ProductCard';
import { money, number } from '@/utils/format';
import { ImpactPanel } from '@/components/ImpactPanel';

export default function BuyerHome() {
  const { t } = useTranslation();
  const { profile } = useAuth();
  const q = useBuyerDashboard();
  const d = q.data;

  return (
    <div className="space-y-6">
      <PageHeader
        title={t('farmer.dashboard.greeting', { name: profile?.full_name ?? '' })}
        actions={<>
          <LinkButton to="/buyer/requests/new">{t('buyer.post_requirement')}</LinkButton>
          <LinkButton to="/buyer/market" variant="outline">{t('nav.market')}</LinkButton>
        </>}
      />

      <section className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {q.isLoading ? Array.from({ length: 4 }).map((_, i) => <StatSkeleton key={i} />) : <>
          <StatCard label={t('buyer.active_orders')} value={String(d?.active_orders ?? 0)} tone="primary" />
          <StatCard label={t('buyer.open_requests')} value={String(d?.open_requests ?? 0)} />
          <StatCard label={t('buyer.total_purchase')} value={money(d?.total_purchase_paise, { compact: true })}
                    tone="secondary" />
          <StatCard label={t('buyer.saved_farmers')} value={String(d?.saved_farmers ?? 0)} />
        </>}
      </section>

      <section className="space-y-3">
        <div className="flex items-center justify-between gap-3">
          <CardTitle>{t('buyer.recommended')}</CardTitle>
          <LinkButton to="/buyer/market" variant="ghost" size="sm">{t('market.view_all')} →</LinkButton>
        </div>
        {q.isLoading ? <CardSkeleton />
          : q.isError ? (
            <ErrorState title={t('common.error_title')} body={t('common.error_body')}
                        retryLabel={t('common.retry')} onRetry={() => void q.refetch()} />
          ) : (d?.recommended ?? []).length === 0 ? (
            <EmptyState title={t('market.no_matches')}
                        action={<LinkButton to="/buyer/market">{t('nav.market')}</LinkButton>} />
          ) : (
            <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
              {d!.recommended.slice(0, 6).map((p) => (
                <ProductCard key={p.id} product={p} to={`/buyer/product/${p.id}`} />
              ))}
            </div>
          )}
      </section>

      {(d?.requests ?? []).length > 0 && (
        <section className="space-y-3">
          <CardTitle>{t('nav.my_requests')}</CardTitle>
          <div className="grid gap-4 sm:grid-cols-2">
            {d!.requests.map((r) => (
              <Card key={r.id} className="space-y-2">
                <div className="flex items-center justify-between gap-2">
                  <h3 className="text-h2 font-semibold text-ink">{r.crop_name}</h3>
                  <Badge tone={r.status === 'open' ? 'success' : 'neutral'}>
                    {t(`market.request_status.${r.status}`)}
                  </Badge>
                </div>
                <p className="tnum text-body text-ink-muted">
                  {number(r.quantity_kg)} {t('common.kg')}
                  {r.target_price_paise != null && ` · ${money(r.target_price_paise)} ${t('common.per_kg')}`}
                </p>
              </Card>
            ))}
          </div>
        </section>
      )}
      {/* Counted from platform records, labelled as such. Sits at the
          end because it is context, not the reason anyone opened this
          page. */}
      <ImpactPanel />
    </div>
  );
}
