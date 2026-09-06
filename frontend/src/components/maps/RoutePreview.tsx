/**
 * Journey preview: pickup marker, destination marker, route, distance, ETA
 * (§6). Shown to the transporter after accepting an offer, before Start
 * Journey -- so they see the actual road route, not just straight-line
 * distance, before committing.
 *
 * Generated from the shipment's stored pickup/drop coordinates only. Never
 * hardcoded, and never re-geocoded -- the same lat/lon the farmer and
 * buyer/arranger picked via LocationPicker.
 */
import { useEffect, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { MapCanvas } from './MapCanvas';
import { number } from '@/utils/format';

interface Props {
  pickup: { lat: number; lon: number; label?: string };
  drop: { lat: number; lon: number; label?: string };
}

export function RoutePreview({ pickup, drop }: Props) {
  const { t } = useTranslation();
  const [summary, setSummary] = useState<{ km: number; mins: number } | null>(null);
  const [routeError, setRouteError] = useState(false);
  const rendererRef = useRef<google.maps.DirectionsRenderer | null>(null);

  useEffect(() => {
    // Recompute if either endpoint changes after the map is already up.
    if (!rendererRef.current) return;
    void requestRoute(rendererRef.current);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [pickup.lat, pickup.lon, drop.lat, drop.lon]);

  const requestRoute = async (renderer: google.maps.DirectionsRenderer) => {
    const maps = window.google?.maps;
    if (!maps) return;
    try {
      const result = await new maps.DirectionsService().route({
        origin: { lat: pickup.lat, lng: pickup.lon },
        destination: { lat: drop.lat, lng: drop.lon },
        travelMode: maps.TravelMode.DRIVING,
      });
      renderer.setDirections(result);
      const leg = result.routes[0]?.legs[0];
      if (leg?.distance && leg?.duration) {
        setSummary({ km: leg.distance.value / 1000, mins: leg.duration.value / 60 });
      }
      setRouteError(false);
    } catch {
      // A straight line between two real, stored points is still useful
      // information even when the Directions API itself is unavailable.
      setRouteError(true);
    }
  };

  return (
    <div className="space-y-3">
      <MapCanvas
        center={{ lat: pickup.lat, lng: pickup.lon }}
        onReady={(map, maps) => {
          new maps.Marker({ position: { lat: pickup.lat, lng: pickup.lon }, map, label: '📍' });
          new maps.Marker({ position: { lat: drop.lat, lng: drop.lon }, map, label: '🏁' });
          const renderer = new maps.DirectionsRenderer({ map, suppressMarkers: true });
          rendererRef.current = renderer;
          void requestRoute(renderer);
          const bounds = new maps.LatLngBounds();
          bounds.extend({ lat: pickup.lat, lng: pickup.lon });
          bounds.extend({ lat: drop.lat, lng: drop.lon });
          map.fitBounds(bounds, 48);
        }}
      />
      {summary ? (
        <div className="flex flex-wrap gap-x-6 gap-y-1 text-body text-ink">
          <span><strong className="tnum">{number(Math.round(summary.km))}</strong> km</span>
          <span><strong className="tnum">{number(Math.round(summary.mins))}</strong> {t('common.min')}</span>
        </div>
      ) : routeError ? (
        <p className="text-label text-ink-muted">{t('maps.route_unavailable')}</p>
      ) : null}
    </div>
  );
}
