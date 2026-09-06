import { useTranslation } from 'react-i18next';
import { useMyCapacity } from '@/hooks/queries';
import {
  Badge, Card, CardSkeleton, EmptyState, ErrorState, LinkButton, PageHeader,
} from '@/components/ui';
import { money, number, date } from '@/utils/format';

export default function Capacity() {
  const { t } = useTranslation();
  const q = useMyCapacity();

  return (
    <div className="space-y-6">
      <PageHeader
        title={t('nav.my_routes')}
        actions={<LinkButton to="/transporter/capacity/new">{t('transporter.route_plan')}</LinkButton>}
      />
      {q.isLoading ? (
        <div className="grid gap-4 sm:grid-cols-2">
          {Array.from({ length: 4 }).map((_, i) => <CardSkeleton key={i} lines={2} />)}
        </div>
      ) : q.isError ? (
        <ErrorState
          title={t('common.error_title')} body={t('common.error_body')}
          retryLabel={t('common.retry')} onRetry={() => void q.refetch()}
        />
      ) : (q.data ?? []).length === 0 ? (
        <EmptyState
          title={t('market.transport_none_title')}
          action={<LinkButton to="/transporter/capacity/new">{t('transporter.route_plan')}</LinkButton>}
        />
      ) : (
        <div className="grid gap-4 sm:grid-cols-2">
          {q.data!.map((c) => (
            <Card key={c.id} className="space-y-3 animate-fade-up">
              <div className="flex flex-wrap items-start justify-between gap-2">
                <h2 className="text-h2 font-semibold text-ink">
                  {c.origin_district ?? '—'} → {c.dest_district ?? '—'}
                </h2>
                <Badge tone={c.status === 'open' ? 'success' : 'neutral'}>{c.status}</Badge>
              </div>

              <dl className="grid grid-cols-2 gap-3">
                <div>
                  <dt className="text-label text-ink-muted">{t('market.available')}</dt>
                  <dd className="tnum text-body font-semibold">
                    {number(c.available_capacity_kg)} / {number(c.total_capacity_kg)} {t('common.kg')}
                  </dd>
                </div>
                <div>
                  <dt className="text-label text-ink-muted">{t('market.price_per_kg')}</dt>
                  <dd className="tnum text-body font-semibold">{money(c.price_paise_per_kg)}</dd>
                </div>
              </dl>

              {c.depart_at && (
                <p className="text-label text-ink-muted">{date(c.depart_at)}</p>
              )}
              {Number(c.discount_pct) > 0 && (
                <Badge tone="warning">−{c.discount_pct}%</Badge>
              )}
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
