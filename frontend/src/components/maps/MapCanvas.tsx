/**
 * The one place a `google.maps.Map` instance gets constructed (§23).
 *
 * Every map on the site (location picker, route preview, live tracking)
 * renders through this. It creates the map exactly once per mount and hands
 * the live `google.maps.Map` object to the caller via `onReady` -- callers
 * then move markers/polylines imperatively (`marker.setPosition(...)`)
 * instead of tearing down and rebuilding the map on every state change,
 * which is what would happen if this were built the usual React-declarative
 * way with a maps wrapper library re-rendering on every prop change.
 *
 * Handles the three ways Maps can fail to appear (§21): not configured for
 * this deployment (no key), failed to load (network/invalid key), and
 * "still loading" -- each gets its own message, never an infinite spinner.
 */
import { useEffect, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { loadGoogleMaps, mapsConfigured, MapsUnavailableError } from '@/services/maps/loadGoogleMaps';
import { Card } from '@/components/ui';

interface Props {
  onReady: (map: google.maps.Map, maps: typeof google.maps) => void;
  center?: { lat: number; lng: number };
  zoom?: number;
  heightClassName?: string;
}

export function MapCanvas({ onReady, center, zoom = 13, heightClassName = 'h-72' }: Props) {
  const { t } = useTranslation();
  const ref = useRef<HTMLDivElement>(null);
  const [error, setError] = useState<'not_configured' | 'failed' | null>(
    mapsConfigured() ? null : 'not_configured',
  );
  const [loading, setLoading] = useState(mapsConfigured());
  const onReadyRef = useRef(onReady);
  onReadyRef.current = onReady;

  useEffect(() => {
    if (!mapsConfigured() || !ref.current) return;
    let cancelled = false;

    loadGoogleMaps()
      .then((maps) => {
        if (cancelled || !ref.current) return;
        const map = new maps.Map(ref.current, {
          center: center ?? { lat: 20.5937, lng: 78.9629 }, // India, sane default
          zoom,
          mapTypeControl: false,
          streetViewControl: false,
          fullscreenControl: false,
        });
        setLoading(false);
        onReadyRef.current(map, maps);
      })
      .catch((err) => {
        if (cancelled) return;
        setLoading(false);
        setError(err instanceof MapsUnavailableError ? 'failed' : 'failed');
      });

    return () => { cancelled = true; };
    // Deliberately empty beyond mount: this effect must run exactly once.
    // Re-running it on every `center`/`zoom` change would recreate the map,
    // which is the exact anti-pattern this component exists to avoid.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  if (error === 'not_configured') {
    return (
      <Card className={`flex ${heightClassName} items-center justify-center bg-surface-low text-center`}>
        <p className="max-w-xs text-label text-ink-muted">{t('maps.not_configured')}</p>
      </Card>
    );
  }
  if (error === 'failed') {
    return (
      <Card className={`flex ${heightClassName} items-center justify-center bg-surface-low text-center`}>
        <p className="max-w-xs text-label text-ink-muted">{t('maps.failed_to_load')}</p>
      </Card>
    );
  }

  return (
    <div className={`relative ${heightClassName} overflow-hidden rounded-md border-card border-outline-variant`}>
      <div ref={ref} className="h-full w-full" />
      {loading && (
        <div className="absolute inset-0 flex items-center justify-center bg-surface-low">
          <p className="text-label text-ink-muted">{t('common.loading')}</p>
        </div>
      )}
    </div>
  );
}
