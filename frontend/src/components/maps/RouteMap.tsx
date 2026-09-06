/**
 * Leaflet + OpenStreetMap route map.
 *
 * Kept as the existing stack (master prompt 32: don't replace working
 * libraries). This module is ONLY ever reached through a dynamic import, so
 * Leaflet's JS and CSS stay out of the initial bundle -- importing the CSS
 * here rather than globally is what makes that work.
 */
import { useEffect, useRef } from 'react';
import { useTranslation } from 'react-i18next';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';

interface Stop { lat: number; lon: number; label?: string | null }

export default function RouteMap({ stops }: { stops: Stop[] }) {
  const el = useRef<HTMLDivElement>(null);
  const map = useRef<L.Map | null>(null);
  const { t } = useTranslation();

  useEffect(() => {
    if (!el.current || map.current) return;
    const points = stops
      .filter((s) => Number.isFinite(s.lat) && Number.isFinite(s.lon))
      .map((s) => [s.lat, s.lon] as [number, number]);
    if (!points.length) return;

    const m = L.map(el.current, { scrollWheelZoom: false });
    map.current = m;

    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
      attribution: '&copy; OpenStreetMap contributors',
      maxZoom: 18,
    }).addTo(m);

    points.forEach((p, i) => {
      // A numbered circle rather than the default pin: it shows stop ORDER,
      // which is the whole point of an optimised route.
      L.marker(p, {
        icon: L.divIcon({
          className: '',
          html: `<span style="display:grid;place-items:center;width:28px;height:28px;
                 border-radius:9999px;background:#006e1c;color:#fff;font:600 13px/1 system-ui;
                 border:2px solid #fff;box-shadow:0 1px 4px rgba(0,0,0,.3)">${i + 1}</span>`,
          iconSize: [28, 28],
          iconAnchor: [14, 14],
        }),
      })
        .addTo(m)
        .bindPopup(stops[i].label ?? `${i + 1}`);
    });

    if (points.length > 1) {
      L.polyline(points, { color: '#006e1c', weight: 4, opacity: 0.85 }).addTo(m);
    }
    m.fitBounds(L.latLngBounds(points), { padding: [32, 32], maxZoom: 13 });

    return () => { m.remove(); map.current = null; };
  }, [stops]);

  return (
    <div
      ref={el}
      role="img"
      aria-label={t('transporter.optimized_route')}
      className="h-72 w-full overflow-hidden rounded-lg border-card border-line-card bg-surface-low"
    />
  );
}
