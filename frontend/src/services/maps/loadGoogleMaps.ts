/**
 * Google Maps JS API loader.
 *
 * The key reaches the browser the same way the Supabase anon key does (A-16):
 * fetched at runtime from GET /api/config, never a VITE_* build-time var
 * baked into the committed bundle. A Maps key is not secret in the same
 * sense an anon key is -- it has to be readable by client-side JS to work at
 * all -- but the actual security boundary is HTTP-referrer restriction in
 * Google Cloud Console, and keeping it out of source is still what stops it
 * leaking into a public repo or a build artifact by accident.
 *
 * Singleton: the script tag is injected once; every caller after the first
 * awaits the same promise. Never creates a second `<script>` tag, and never
 * throws past a caller that's prepared to render a fallback -- every
 * consumer of this module is expected to render a "Maps not configured" /
 * "Maps failed to load" state rather than crash (spec §21).
 */
import { getConfig } from '@/services/supabase/client';

let loadPromise: Promise<typeof google.maps> | null = null;

export class MapsUnavailableError extends Error {}

/** True once GET /api/config has resolved and it named a non-empty key. Does
    NOT mean the script has loaded -- callers still need loadGoogleMaps(). */
export function mapsConfigured(): boolean {
  return Boolean(getConfig()?.google_maps_api_key);
}

export function loadGoogleMaps(): Promise<typeof google.maps> {
  if (loadPromise) return loadPromise;

  const key = getConfig()?.google_maps_api_key;
  if (!key) {
    return Promise.reject(new MapsUnavailableError(
      'Google Maps is not configured for this deployment.'
    ));
  }

  loadPromise = new Promise((resolve, reject) => {
    const existing = document.getElementById('udgam-google-maps') as HTMLScriptElement | null;
    if (existing && (window as unknown as { google?: typeof google }).google?.maps) {
      resolve((window as unknown as { google: typeof google }).google.maps);
      return;
    }

    const callbackName = '__udgamGoogleMapsReady';
    (window as unknown as Record<string, () => void>)[callbackName] = () => {
      resolve((window as unknown as { google: typeof google }).google.maps);
    };

    const script = document.createElement('script');
    script.id = 'udgam-google-maps';
    script.async = true;
    script.defer = true;
    // 'places' for the pickup/drop autocomplete; 'geometry' for the polyline/
    // distance helpers the route preview and geofence display use.
    script.src = `https://maps.googleapis.com/maps/api/js?key=${encodeURIComponent(key)}`
      + `&libraries=places,geometry&callback=${callbackName}&loading=async`;
    script.onerror = () => {
      loadPromise = null; // let a later render retry rather than staying stuck
      reject(new MapsUnavailableError('Google Maps failed to load.'));
    };
    document.head.appendChild(script);
  });

  return loadPromise;
}
