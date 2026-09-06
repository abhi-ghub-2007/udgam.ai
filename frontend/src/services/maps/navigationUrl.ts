/**
 * Google Maps navigation link (§7).
 *
 * Generated from the shipment's own stored coordinates, never hardcoded.
 * Uses the public Maps URL API (`google.com/maps/dir/?api=1`), which works
 * identically on desktop browsers and mobile (where it hands off to the
 * Google Maps app if installed) with no SDK or API key of our own required
 * for the link itself -- this is navigation, a separate concern from the
 * in-app live tracking built on our own geolocation + realtime pipeline.
 */
export function buildNavigationUrl(
  origin: { lat: number; lon: number },
  destination: { lat: number; lon: number },
): string {
  const params = new URLSearchParams({
    api: '1',
    origin: `${origin.lat},${origin.lon}`,
    destination: `${destination.lat},${destination.lon}`,
    travelmode: 'driving',
  });
  return `https://www.google.com/maps/dir/?${params.toString()}`;
}
