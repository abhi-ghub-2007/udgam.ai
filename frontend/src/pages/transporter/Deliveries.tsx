/**
 * The transporter's journey page (§6/§7/§8/§11).
 *
 * Route preview before starting, a farmer-confirmation gate before pickup can
 * be marked, Start Journey (which begins OUR OWN live tracking first, then
 * offers Google Maps navigation separately -- §22's mandatory distinction),
 * and real checkpoints derived from the shipment's own timestamps.
 */
import { useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import {
  useShipments, useShipmentCheckpoints, useUpdateShipmentStatus,
} from '@/hooks/queries';
import { useLiveLocationBroadcast } from '@/hooks/useLiveLocationBroadcast';
import { ApiError } from '@/services/api/client';
import { buildNavigationUrl } from '@/services/maps/navigationUrl';
import { RoutePreview } from '@/components/maps/RoutePreview';
import {
  Badge, Button, Card, CardSkeleton, CardTitle, EmptyState, ErrorState, PageHeader, cx,
} from '@/components/ui';
import { ShipmentTimeline } from '@/components/ShipmentTimeline';
import { money, number, date } from '@/utils/format';
import type { ShipmentStatus } from '@/types/api';

const NEXT_STEP: Partial<Record<ShipmentStatus, { to: 'picked_up' | 'in_transit' | 'arrived'; labelKey: string }>> = {
  assigned: { to: 'picked_up', labelKey: 'market.i_have_picked_up' },
  picked_up: { to: 'in_transit', labelKey: 'market.start_journey' },
  in_transit: { to: 'arrived', labelKey: 'market.mark_arrived' },
};

export default function Deliveries() {
  const { id } = useParams();
  const { t } = useTranslation();
  const navigate = useNavigate();
  const q = useShipments();
  const checkpoints = useShipmentCheckpoints(id);
  const update = useUpdateShipmentStatus(id);
  const [error, setError] = useState<string | null>(null);

  const s = (q.data ?? []).find((x) => x.id === id);
  const tracking = useLiveLocationBroadcast(id, s?.status === 'in_transit');

  if (q.isLoading) return <CardSkeleton lines={5} />;
  if (q.isError) {
    return (
      <ErrorState
        title={t('common.error_title')} body={t('common.error_body')}
        retryLabel={t('common.retry')} onRetry={() => void q.refetch()}
      />
    );
  }
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
  const hasCoords = s.pickup_lat != null && s.pickup_lon != null && s.drop_lat != null && s.drop_lon != null;
  const pickupNotConfirmed = s.status === 'assigned' && !s.pickup_confirmed_at;

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

        {/* Real checkpoints, from the shipment's own timestamps -- never a
            frontend-only fake state (§11). */}
        {checkpoints.data && (
          <ul className="flex flex-wrap gap-x-4 gap-y-1 border-t border-line-card pt-3 text-label">
            {checkpoints.data.checkpoints.map((c) => (
              <li key={c.code} className={cx(c.done ? 'text-primary' : 'text-ink-muted')}>
                {c.done ? '✓' : '○'} {t(`market.checkpoint_${c.code}`)}
              </li>
            ))}
          </ul>
        )}

        <dl className="grid gap-3 border-t border-line-card pt-4 sm:grid-cols-2">
          {dist != null && (
            <div>
              <dt className="text-label text-ink-muted">{t('market.distance_label')}</dt>
              <dd className="tnum text-body font-semibold">{number(Math.round(dist))} km</dd>
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

        {/* Preview the actual road route before committing to the job. */}
        {hasCoords && s.status !== 'delivered' && s.status !== 'cancelled' && (
          <div className="border-t border-line-card pt-4">
            <CardTitle className="text-body">{t('market.journey_preview')}</CardTitle>
            <div className="mt-2">
              <RoutePreview
                pickup={{ lat: s.pickup_lat!, lon: s.pickup_lon! }}
                drop={{ lat: s.drop_lat!, lon: s.drop_lon! }}
              />
            </div>
          </div>
        )}

        {pickupNotConfirmed && (
          <p className="rounded-md bg-surface-low px-3 py-2 text-label text-ink-muted">
            {t('market.awaiting_farmer_pickup_confirmation')}
          </p>
        )}

        {s.status === 'in_transit' && (
          <div className="space-y-2 border-t border-line-card pt-4">
            <p className="text-label text-ink-muted">
              {tracking.status === 'active' && t('market.tracking_active')}
              {tracking.status === 'requesting' && t('market.tracking_requesting')}
              {tracking.status === 'denied' && t('market.tracking_denied')}
              {tracking.status === 'unavailable' && t('market.tracking_unavailable')}
              {tracking.status === 'error' && t('market.tracking_error')}
            </p>
            {hasCoords && (
              <a
                href={buildNavigationUrl(
                  { lat: s.current_lat ?? s.pickup_lat!, lon: s.current_lon ?? s.pickup_lon! },
                  { lat: s.drop_lat!, lon: s.drop_lon! },
                )}
                target="_blank" rel="noopener noreferrer"
                className="inline-block min-h-tap rounded-md bg-secondary px-5 py-3 text-body font-semibold text-secondary-on"
              >
                {t('market.navigate_with_maps')}
              </a>
            )}
          </div>
        )}

        {error && (
          <p role="alert" className="rounded-md bg-danger-container px-3 py-2 text-body text-danger-on-container">
            {error}
          </p>
        )}

        <div className="flex flex-wrap gap-3">
          {step && !(step.to === 'picked_up' && pickupNotConfirmed) && (
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
