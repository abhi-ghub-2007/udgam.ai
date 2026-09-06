import { useTranslation } from 'react-i18next';
import { useShipments } from '@/hooks/queries';
import { Badge, Card, CardSkeleton, EmptyState, ErrorState, LinkButton, PageHeader } from '@/components/ui';
import { ShipmentTimeline } from '@/components/ShipmentTimeline';
import { number, date } from '@/utils/format';

export default function Transport() {
  const { t } = useTranslation();
  const q = useShipments();
  const rows = q.data ?? [];

  return (
    <div className="space-y-6">
      <PageHeader title={t('market.transport_title')} subtitle={t('market.transport_intro')} />
      {q.isLoading ? <CardSkeleton lines={3} />
        : q.isError ? (
          <ErrorState title={t('common.error_title')} body={t('common.error_body')}
                      retryLabel={t('common.retry')} onRetry={() => void q.refetch()} />
        ) : rows.length === 0 ? (
          <EmptyState title={t('market.transport_none_title')} body={t('market.transport_empty')}
                      action={<LinkButton to="/farmer/orders">{t('market.orders_title')}</LinkButton>} />
        ) : (
          <div className="space-y-4">
            {rows.map((s) => {
              const dist = s.actual_distance_km ?? s.planned_distance_km;
              return (
                <Card key={s.id} className="space-y-4 animate-fade-up">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <h2 className="text-h2 font-semibold text-ink">{s.order_no ?? t('market.shipment')}</h2>
                    <Badge tone={s.status === 'delivered' ? 'success' : s.status === 'cancelled' ? 'danger' : 'info'}>
                      {t(`market.shipment_step.${s.status}`)}
                    </Badge>
                  </div>
                  <ShipmentTimeline status={s.status} />
                  <div className="flex flex-wrap gap-x-5 gap-y-1 text-label text-ink-muted">
                    {dist != null && <span>{t('market.distance_label')}: {number(Math.round(dist))} km</span>}
                    {s.eta_at && s.status !== 'delivered' && <span>{t('market.eta')}: {date(s.eta_at)}</span>}
                    {s.picked_up_at && <span>{t('market.picked_up_on')}: {date(s.picked_up_at)}</span>}
                    {s.delivered_at && <span>{t('market.delivered_on')}: {date(s.delivered_at)}</span>}
                  </div>
                </Card>
              );
            })}
          </div>
        )}
    </div>
  );
}
