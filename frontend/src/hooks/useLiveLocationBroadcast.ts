/**
 * The transporter's own device -> our backend (§8/§9/§22).
 *
 * This is the ONLY place a transporter's coordinates come from. Opening
 * Google Maps for turn-by-turn navigation (separately, in JourneyView) does
 * not and cannot feed this -- Google Maps has no channel back to us. This
 * hook is `navigator.geolocation.watchPosition`, throttled, posted to
 * POST /shipments/{id}/location, which the backend also throttles and uses
 * to auto-detect arrival by geofence.
 *
 * Throttle is dual: a minimum time between sends AND a minimum distance
 * moved, so a transporter stopped at a dhaba does not spam updates every
 * `MIN_INTERVAL_MS` for no reason, but a fast-moving vehicle still reports
 * often enough to look "live" on the map.
 */
import { useEffect, useRef, useState } from 'react';
import { useMutation } from '@tanstack/react-query';
import { api } from '@/services/api/client';

const MIN_INTERVAL_MS = 6_000;
const MIN_DISTANCE_M = 25;

export type LocationTrackingStatus =
  | 'idle' | 'requesting' | 'active' | 'denied' | 'unavailable' | 'error';

function distanceMeters(a: GeolocationCoordinates, lat: number, lon: number): number {
  const R = 6371000;
  const dLat = ((lat - a.latitude) * Math.PI) / 180;
  const dLon = ((lon - a.longitude) * Math.PI) / 180;
  const s = Math.sin(dLat / 2) ** 2
    + Math.cos((a.latitude * Math.PI) / 180) * Math.cos((lat * Math.PI) / 180)
    * Math.sin(dLon / 2) ** 2;
  return 2 * R * Math.asin(Math.sqrt(s));
}

export function useLiveLocationBroadcast(shipmentId: string | undefined, enabled: boolean) {
  const [status, setStatus] = useState<LocationTrackingStatus>('idle');
  const [lastSentAt, setLastSentAt] = useState<number | null>(null);
  const watchId = useRef<number | null>(null);
  const lastSent = useRef<{ t: number; lat: number; lon: number } | null>(null);

  const send = useMutation({
    mutationFn: (body: { lat: number; lon: number; accuracy_m?: number; heading?: number; speed_kmph?: number }) =>
      api.post<{ ok: boolean; arrived: boolean }>(`/api/shipments/${shipmentId}/location`, body),
  });

  useEffect(() => {
    if (!enabled || !shipmentId) {
      if (watchId.current != null) navigator.geolocation.clearWatch(watchId.current);
      watchId.current = null;
      setStatus('idle');
      return undefined;
    }

    if (!('geolocation' in navigator)) {
      setStatus('unavailable');
      return undefined;
    }

    setStatus('requesting');
    const id = navigator.geolocation.watchPosition(
      (pos) => {
        setStatus('active');
        const now = Date.now();
        const { latitude, longitude, accuracy, heading, speed } = pos.coords;
        const prior = lastSent.current;
        const movedEnough = !prior || distanceMeters(pos.coords, prior.lat, prior.lon) >= MIN_DISTANCE_M;
        const enoughTimePassed = !prior || now - prior.t >= MIN_INTERVAL_MS;
        // Send on time OR distance, whichever comes first -- a stopped
        // vehicle still refreshes "last updated" periodically instead of
        // going silent forever.
        if (!prior || movedEnough || enoughTimePassed) {
          lastSent.current = { t: now, lat: latitude, lon: longitude };
          setLastSentAt(now);
          send.mutate({
            lat: latitude, lon: longitude,
            accuracy_m: accuracy ?? undefined,
            heading: heading ?? undefined,
            speed_kmph: speed != null ? speed * 3.6 : undefined, // m/s -> km/h
          });
        }
      },
      (err) => {
        setStatus(err.code === err.PERMISSION_DENIED ? 'denied' : 'error');
      },
      { enableHighAccuracy: true, maximumAge: 5_000, timeout: 20_000 },
    );
    watchId.current = id;

    return () => {
      navigator.geolocation.clearWatch(id);
      watchId.current = null;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps -- `send` (a mutation object) is stable enough per shipmentId; re-creating the watch on every render would thrash geolocation permissions.
  }, [shipmentId, enabled]);

  return { status, lastSentAt, arrived: send.data?.arrived ?? false };
}
