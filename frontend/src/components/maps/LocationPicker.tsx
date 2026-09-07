/**
 * Pickup/drop location selection via Google Places (§5).
 *
 * Search a place, see it on the map, drag the pin to correct it, confirm.
 * Emits { address, lat, lon, place_id } -- coordinates are what route
 * generation, distance, live tracking and the geofence all need; storing
 * the address string alone (what this form replaces) gave none of that.
 *
 * Uses `google.maps.places.PlaceAutocompleteElement`, NOT the classic
 * `Autocomplete` widget this file used to bind to a plain `<input>`. Verified
 * live in a real browser against the project's actual API key: the classic
 * widget throws `LegacyApiNotActivatedMapError` ("You're calling a legacy
 * API, which is not enabled for your project") because this Cloud project
 * has "Places API (New)" enabled, not the legacy "Places API" the old widget
 * depends on -- and per Google's own console warning, the legacy widget "is
 * not available to new customers" as of March 2025, so telling the user to
 * just enable the legacy API in Console is not a reliable fix. The base
 * `Map`/`Marker` calls used elsewhere on this page are a different, older
 * product (Maps JavaScript API) that this project does have enabled, which
 * is why only the autocomplete search box was broken and the map itself
 * rendered fine.
 *
 * `PlaceAutocompleteElement` is a form-associated custom element with a
 * closed shadow root -- it renders its own internal input rather than
 * binding to one of ours, so it is mounted imperatively into a container div
 * instead of through JSX (no ambient type for the tag, and no need for one).
 */
import { useEffect, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { MapCanvas } from './MapCanvas';

export interface PickedLocation {
  address: string;
  lat: number;
  lon: number;
  place_id: string | null;
}

interface Props {
  id: string;
  value: PickedLocation | null;
  onChange: (loc: PickedLocation) => void;
  placeholder?: string;
}

export function LocationPicker({ id, value, onChange, placeholder }: Props) {
  const { t } = useTranslation();
  const containerRef = useRef<HTMLDivElement>(null);
  const elRef = useRef<InstanceType<typeof google.maps.places.PlaceAutocompleteElement> | null>(null);
  const mapRef = useRef<google.maps.Map | null>(null);
  const markerRef = useRef<google.maps.Marker | null>(null);
  const mapsRef = useRef<typeof google.maps | null>(null);
  const onChangeRef = useRef(onChange);
  onChangeRef.current = onChange;
  // The widget owns its own displayed text (closed shadow root); this is
  // only what we show while its predictions API is still loading, and lets
  // a reverse-geocoded address (from a map click, not a search) show even
  // before the autocomplete element itself exists.
  const [pendingAddress, setPendingAddress] = useState(value?.address ?? '');
  // MapCanvas's `onReady` fires imperatively and only ever WRITES to
  // `mapRef`/`mapsRef` -- mutating a ref never causes a re-render, so an
  // effect keyed on `mapRef.current` could only ever "notice" the map became
  // ready if something UNRELATED happened to re-render this component
  // afterwards. That's what the previous version of this file (both under
  // the old `Autocomplete` widget and briefly under this rewrite) actually
  // did: it worked, but only by accident, whenever a sibling state update
  // elsewhere in the form happened to re-render this component after the
  // map resolved. This counter is bumped from inside `onReady` itself so the
  // mount effect below reliably runs the moment the map is actually ready.
  const [mapReadyTick, setMapReadyTick] = useState(0);

  const placeAt = (maps: typeof google.maps, map: google.maps.Map, lat: number, lon: number) => {
    const pos = { lat, lng: lon };
    if (markerRef.current) {
      markerRef.current.setPosition(pos);
    } else {
      markerRef.current = new maps.Marker({ position: pos, map, draggable: true });
      markerRef.current.addListener('dragend', () => {
        const p = markerRef.current!.getPosition();
        if (!p) return;
        reverseGeocode(maps, p.lat(), p.lng());
      });
    }
    map.panTo(pos);
    map.setZoom(15);
  };

  const reverseGeocode = (maps: typeof google.maps, lat: number, lon: number) => {
    new maps.Geocoder().geocode({ location: { lat, lng: lon } }, (results, status) => {
      const addr = status === 'OK' && results?.[0] ? results[0].formatted_address : pendingAddress;
      setPendingAddress(addr);
      if (elRef.current) elRef.current.value = addr;
      onChangeRef.current({ address: addr, lat, lon, place_id: results?.[0]?.place_id ?? null });
    });
  };

  useEffect(() => {
    if (!mapsRef.current || !containerRef.current || elRef.current) return;
    const maps = mapsRef.current;
    const el = new maps.places.PlaceAutocompleteElement({
      // The seed data and every demo account is Indian; this only narrows
      // suggestion ranking, it does not block picking a place outside India.
      includedRegionCodes: ['in'],
    });
    el.id = id;
    el.style.width = '100%';
    if (value?.address) el.value = value.address;
    else if (pendingAddress) el.value = pendingAddress;
    if (placeholder) {
      // PlaceAutocompleteElement doesn't take a `placeholder` constructor
      // option in this API version; setting the attribute is the documented
      // fallback and degrades harmlessly (ignored) if a future version does
      // support the option instead.
      el.setAttribute('placeholder', placeholder);
    }
    containerRef.current.appendChild(el);
    elRef.current = el;

    const onSelect = async (e: Event) => {
      const evt = e as unknown as { placePrediction: google.maps.places.PlacePrediction };
      const place = evt.placePrediction.toPlace();
      await place.fetchFields({ fields: ['displayName', 'formattedAddress', 'location', 'id'] });
      const loc = place.location;
      if (!loc || !mapRef.current) return;
      const lat = loc.lat();
      const lon = loc.lng();
      const addr = place.formattedAddress ?? place.displayName ?? '';
      setPendingAddress(addr);
      onChangeRef.current({ address: addr, lat, lon, place_id: place.id ?? null });
      placeAt(maps, mapRef.current, lat, lon);
    };
    el.addEventListener('gmp-select', onSelect);

    return () => {
      el.removeEventListener('gmp-select', onSelect);
      el.remove();
      elRef.current = null;
    };
    // Mount once the map (and therefore `google.maps.places`) is ready --
    // `mapReadyTick` (a real state value, not a ref) is what makes this
    // dependency actually fire; see the comment where it's declared.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [mapReadyTick]);

  return (
    <div className="space-y-2">
      <div ref={containerRef} id={`${id}-mount`} />
      <p className="text-label text-ink-muted">{t('maps.search_hint')}</p>
      <MapCanvas
        heightClassName="h-56"
        center={value ? { lat: value.lat, lng: value.lon } : undefined}
        onReady={(map, maps) => {
          mapRef.current = map;
          mapsRef.current = maps;
          if (value) placeAt(maps, map, value.lat, value.lon);
          map.addListener('click', (e: google.maps.MapMouseEvent) => {
            if (!e.latLng) return;
            reverseGeocode(maps, e.latLng.lat(), e.latLng.lng());
            placeAt(maps, map, e.latLng.lat(), e.latLng.lng());
          });
          setMapReadyTick((n) => n + 1);
        }}
      />
    </div>
  );
}
