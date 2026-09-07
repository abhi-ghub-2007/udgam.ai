/**
 * The two confirmation gates plus live tracking (§3/§10/§13).
 *
 * Farmer confirms the produce is ready and handed over -- BEFORE the
 * transporter can start the journey, not after. Buyer confirms delivery
 * actually happened -- the transporter reaching the destination (or a GPS
 * geofence detecting it) never completes the order by itself. Both render
 * on the same shared order page, gated by role and shipment status, so
 * neither side ever sees a button for a decision that is not theirs to make.
 */
import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useConfirmPickup, useConfirmDelivery } from '@/hooks/queries';
import { useShipmentRealtime } from '@/hooks/useShipmentRealtime';
import { ApiError } from '@/services/api/client';
import { LiveTrackingMap } from '@/components/maps/LiveTrackingMap';
import { Badge, Button, Card, CardTitle } from '@/components/ui';
import { date } from '@/utils/format';
import type { ShipmentDetails, ShipmentStatus } from '@/types/api';

export function TrackingPanel({ shipment, isFarmer, isBuyer, onDone }: {
  shipment: ShipmentDetails;
  isFarmer: boolean;
  isBuyer: boolean;
  onDone: () => void;
}) {
  const { t } = useTranslation();
  const confirmPickup = useConfirmPickup(shipment.id);
  const confirmDelivery = useConfirmDelivery(shipment.id);
  const [error, setError] = useState<string | null>(null);
  const [live, setLive] = useState<{ lat: number; lon: number; heading: number | null } | null>(
    shipment.current_lat != null && shipment.current_lon != null
      ? { lat: shipment.current_lat, lon: shipment.current_lon, heading: shipment.current_heading }
      : null,
  );
  const [connection, setConnection] = useState<'connecting' | 'connected' | 'disconnected'>('connecting');
  // Realtime patches for fields the gates/badges actually read -- status,
  // pickup_confirmed_at, location_updated_at. Without this, only the marker
  // on the map moved live; the "Confirm Delivery" hint text and status badge
  // sat frozen at whatever they were when the page loaded, until the viewer's
  // own action (or a manual reload) forced a refetch. The two `useState`
  // above have the same shape of bug: their initial value is only computed
  // once, so if this component stays mounted across a navigation to a
  // DIFFERENT order's tracking page (React Router reuses the element, it
  // doesn't remount), stale state from the previous shipment would linger.
  const [patch, setPatch] = useState<Partial<ShipmentDetails>>({});

  useEffect(() => {
    // A new shipment (new order navigated to, or first mount) starts clean --
    // otherwise the previous shipment's live position/status could flash on
    // screen for the new one until its own realtime events arrive.
    setPatch({});
    setLive(
      shipment.current_lat != null && shipment.current_lon != null
        ? { lat: shipment.current_lat, lon: shipment.current_lon, heading: shipment.current_heading }
        : null,
    );
    setConnection('connecting');
    // eslint-disable-next-line react-hooks/exhaustive-deps -- reset keyed on identity change only, not every field of `shipment`.
  }, [shipment.id]);

  const live_shipment: ShipmentDetails = { ...shipment, ...patch };

  // The buyer and farmer both watch the SAME row update over Realtime -- this
  // is the "our app tracks the transporter" half of §22, entirely separate
  // from whatever Google Maps navigation the transporter opened.
  useShipmentRealtime(
    shipment.id,
    (row) => {
      if (row.current_lat != null && row.current_lon != null) {
        setLive({ lat: row.current_lat, lon: row.current_lon, heading: row.current_heading ?? null });
      }
      // Status transitions the transporter/geofence make on their own (most
      // notably the geofence auto-setting 'arrived') must reach this page
      // without the viewer having clicked anything themselves.
      const { status, pickup_confirmed_at, location_updated_at, arrived_at, delivered_at } = row;
      setPatch((prev) => ({
        ...prev,
        ...(status !== undefined ? { status: status as ShipmentStatus } : {}),
        ...(pickup_confirmed_at !== undefined ? { pickup_confirmed_at } : {}),
        ...(location_updated_at !== undefined ? { location_updated_at } : {}),
        ...(arrived_at !== undefined ? { arrived_at } : {}),
        ...(delivered_at !== undefined ? { delivered_at } : {}),
      }));
    },
    setConnection,
  );

  const onConfirmPickup = async () => {
    setError(null);
    try {
      await confirmPickup.mutateAsync();
      onDone();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : t('common.error_body'));
    }
  };

  const onConfirmDelivery = async () => {
    setError(null);
    try {
      await confirmDelivery.mutateAsync();
      onDone();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : t('common.error_body'));
    }
  };

  const showPickupGate = isFarmer && live_shipment.status === 'assigned' && !live_shipment.pickup_confirmed_at;
  const showTrackingMap = ['picked_up', 'in_transit', 'arrived'].includes(live_shipment.status);
  const showDeliveryGate = isBuyer && ['in_transit', 'arrived'].includes(live_shipment.status);

  if (!showPickupGate && !showTrackingMap && !showDeliveryGate) return null;

  return (
    <Card className="space-y-4">
      <CardTitle>{t('market.transport_tracking')}</CardTitle>

      {error && (
        <p role="alert" className="rounded-md bg-danger-container px-3 py-2 text-body text-danger-on-container">
          {error}
        </p>
      )}

      {showPickupGate && (
        <div className="space-y-2">
          <p className="text-body text-ink-muted">{t('market.confirm_pickup_hint')}</p>
          <Button loading={confirmPickup.isPending} onClick={() => void onConfirmPickup()}>
            {t('market.confirm_pickup')}
          </Button>
        </div>
      )}
      {isFarmer && live_shipment.pickup_confirmed_at && live_shipment.status === 'assigned' && (
        <Badge tone="success">{t('market.pickup_confirmed_at', { date: date(live_shipment.pickup_confirmed_at) })}</Badge>
      )}

      {showTrackingMap && (
        <div className="space-y-2">
          <div className="flex items-center justify-between gap-2">
            <Badge tone={live_shipment.status === 'arrived' ? 'success' : 'info'}>
              {t(`market.shipment_step.${live_shipment.status}`)}
            </Badge>
            <span className="text-label text-ink-muted">
              {connection === 'connected' ? t('market.live_connected')
                : connection === 'disconnected' ? t('market.live_disconnected')
                : t('market.live_connecting')}
            </span>
          </div>
          <LiveTrackingMap
            pickup={shipment.pickup_lat != null ? { lat: shipment.pickup_lat, lon: shipment.pickup_lon! } : null}
            drop={shipment.drop_lat != null ? { lat: shipment.drop_lat, lon: shipment.drop_lon! } : null}
            transporter={live}
          />
          {live_shipment.location_updated_at && (
            <p className="text-label text-ink-muted">
              {t('market.last_updated')} {date(live_shipment.location_updated_at)}
            </p>
          )}
        </div>
      )}

      {showDeliveryGate && (
        <div className="space-y-2 border-t border-line-card pt-4">
          <p className="text-body text-ink-muted">
            {live_shipment.status === 'arrived' ? t('market.arrived_confirm_hint') : t('market.confirm_delivery_early_hint')}
          </p>
          <Button loading={confirmDelivery.isPending} onClick={() => void onConfirmDelivery()}>
            {t('order.confirm_delivery')}
          </Button>
        </div>
      )}
    </Card>
  );
}
