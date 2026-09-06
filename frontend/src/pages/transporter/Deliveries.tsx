import { useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { useShipments, useUpdateShipmentStatus } from '@/hooks/queries';
import { ApiError } from '@/services/api/client';
import {
  Badge, Button, Card, CardSkeleton, EmptyState, ErrorState, PageHeader,
} from '@/components/ui';
import { ShipmentTimeline } from '@/components/ShipmentTimeline';
import { money, number, date } from '@/utils/format';
import type { ShipmentStatus } from '@/types/api';

/** The one legal next step from where the shipment is now. This page used to
    be read-only -- status could only ever be 'assigned' or 'created' forever,
    because nothing anywhere called POST /shipments/{id}/status. */
const NEXT_STEP: Partial<Record<ShipmentStatus, { to: 'picked_up' | 'in_transit' | 'delivered'; labelKey: string }>> = {
  assigned: { to: 'picked_up', labelKey: 'market.confirm_pickup' },
  picked_up: { to: 'in_transit', labelKey: 'market.mark_in_transit' },
  in_transit: { to: 'delivered', labelKey: 'market.mark_delivered' },
};

export default function Deliveries() {
  const { id } = useParams();
  const { t } = useTranslation();
  const navigate = useNavigate();
  const q = useShipments();
  // Hooks must run unconditionally, so this is called before any early
  // return below -- mutating a shipment that may not exist yet is harmless
  // since the button using it only renders once `s` is confirmed real.
  const update = useUpdateShipmentStatus(id);
  const [error, setError] = useState<string | null>(null);

  if (q.isLoading) return <CardSkeleton lines={5} />;
  if (q.isError) {
    return (
      <ErrorState
        title={t('common.error_title')} body={t('common.error_body')}
        retryLabel={t('common.retry')} onRetry={() => void q.refetch()}
      />
    );
  }

  const s = (q.data ?? []).find((x) => x.id === id);
  if (!s) {
    return (
      <div className="space-y-6">
        <PageHeader title={t('market.shipment')} />
        <EmptyState title={t('common.not_found_title')} />
      </div>
    );
  }

  const dist = s.actual_distance_km ?? s.planned_distance_km;
  const step = NEXT_STEP[s.status];

  const onAdvance = async () => {
    if (!step) return;
    setError(null);
    try {
      await update.mutateAsync(step.to);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : t('common.error_body'));
    }
  };

  return (
    <div className="space-y-6">
      <PageHeader title={s.order_no ?? t('market.shipment')} />
      <Card className="max-w-2xl space-y-5">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <Badge tone={s.status === 'delivered' ? 'success' : s.status === 'cancelled' ? 'danger' : 'info'}>
            {t(`market.shipment_step.${s.status}`)}
          </Badge>
          <span className="tnum text-h2 font-bold text-primary">{money(s.earnings_paise)}</span>
        </div>

        <ShipmentTimeline status={s.status} />

        <dl className="grid gap-3 border-t border-line-card pt-4 sm:grid-cols-2">
          {dist != null && (
            <div>
              <dt className="text-label text-ink-muted">{t('market.distance_label')}</dt>
              <dd className="tnum text-body font-semibold">{number(Math.round(dist))} km</dd>
            </div>
          )}
          {s.eta_at && (
            <div>
              <dt className="text-label text-ink-muted">{t('market.eta')}</dt>
              <dd className="text-body font-semibold">{date(s.eta_at)}</dd>
            </div>
          )}
          {s.picked_up_at && (
            <div>
              <dt className="text-label text-ink-muted">{t('market.picked_up_on')}</dt>
              <dd className="text-body font-semibold">{date(s.picked_up_at)}</dd>
            </div>
          )}
          {s.delivered_at && (
            <div>
              <dt className="text-label text-ink-muted">{t('market.delivered_on')}</dt>
              <dd className="text-body font-semibold">{date(s.delivered_at)}</dd>
            </div>
          )}
        </dl>

        {error && (
          <p role="alert" className="rounded-md bg-danger-container px-3 py-2 text-body text-danger-on-container">
            {error}
          </p>
        )}

        <div className="flex flex-wrap gap-3">
          {step && (
            <Button loading={update.isPending} onClick={() => void onAdvance()}>
              {t(step.labelKey)}
            </Button>
          )}
          <Button variant="outline" onClick={() => navigate(-1)}>{t('common.back')}</Button>
        </div>
      </Card>
    </div>
  );
}
