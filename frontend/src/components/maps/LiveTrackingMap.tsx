/**
 * The buyer/farmer "where is my produce" map (§10).
 *
 * The map is created once. Every subsequent position update from
 * useShipmentRealtime moves the SAME marker (`marker.setPosition`) rather
 * than tearing the map down -- see MapCanvas's own comment for why that
 * matters. Pickup and destination markers are static; the transporter marker
 * is the only one that moves, and can rotate to face `heading` when the
 * backend has one.
 */
import { useEffect, useRef } from 'react';
import { useTranslation } from 'react-i18next';
import { MapCanvas } from './MapCanvas';

interface Props {
  pickup?: { lat: number; lon: number } | null;
  drop?: { lat: number; lon: number } | null;
  transporter: { lat: number; lon: number; heading?: number | null } | null;
}

export function LiveTrackingMap({ pickup, drop, transporter }: Props) {
  const { t } = useTranslation();
  const transporterMarkerRef = useRef<google.maps.Marker | null>(null);
  const mapRef = useRef<google.maps.Map | null>(null);
  const mapsRef = useRef<typeof google.maps | null>(null);

  // Position updates after the map exists move the marker in place -- this
  // is the whole point of holding the map/marker in refs instead of state.
  useEffect(() => {
    if (!transporter || !mapsRef.current) return;
    const pos = { lat: transporter.lat, lng: transporter.lon };
    if (transporterMarkerRef.current) {
      transporterMarkerRef.current.setPosition(pos);
      if (transporter.heading != null) {
        transporterMarkerRef.current.setIcon({
          path: mapsRef.current.SymbolPath.FORWARD_CLOSED_ARROW,
          scale: 5, rotation: transporter.heading,
          fillColor: '#006e1c', fillOpacity: 1, strokeWeight: 1, strokeColor: '#fff',
        });
      }
    } else if (mapRef.current) {
      transporterMarkerRef.current = new mapsRef.current.Marker({
        position: pos, map: mapRef.current, label: '🚚', zIndex: 10,
      });
    }
  }, [transporter?.lat, transporter?.lon, transporter?.heading]);

  return (
    <div className="space-y-2">
      <MapCanvas
        center={transporter ? { lat: transporter.lat, lng: transporter.lon }
              : pickup ? { lat: pickup.lat, lng: pickup.lon } : undefined}
        onReady={(map, maps) => {
          mapRef.current = map;
          mapsRef.current = maps;
          const bounds = new maps.LatLngBounds();
          if (pickup) {
            new maps.Marker({ position: { lat: pickup.lat, lng: pickup.lon }, map, label: '📍' });
            bounds.extend({ lat: pickup.lat, lng: pickup.lon });
          }
          if (drop) {
            new maps.Marker({ position: { lat: drop.lat, lng: drop.lon }, map, label: '🏁' });
            bounds.extend({ lat: drop.lat, lng: drop.lon });
          }
          if (transporter) {
            transporterMarkerRef.current = new maps.Marker({
              position: { lat: transporter.lat, lng: transporter.lon }, map, label: '🚚', zIndex: 10,
            });
            bounds.extend({ lat: transporter.lat, lng: transporter.lon });
          }
          if (!bounds.isEmpty()) map.fitBounds(bounds, 64);
        }}
      />
      {!transporter && (
        <p className="text-label text-ink-muted">{t('market.waiting_for_location')}</p>
      )}
    </div>
  );
}
