/**
 * Pickup/drop location selection via Google Places (§5).
 *
 * Search a place, see it on the map, drag the pin to correct it, confirm.
 * Emits { address, lat, lon, place_id } -- coordinates are what route
 * generation, distance, live tracking and the geofence all need; storing
 * the address string alone (what this form replaces) gave none of that.
 *
 * Uses the classic `Autocomplete` widget rather than the newer
 * `PlaceAutocompleteElement`: the latter is a custom element that needs the
 * `places` library's web-component bootstrapping and a different event
 * model, while `Autocomplete` binds directly to a plain `<input>` -- which
 * is what lets this drop into the existing Field/Input components used
 * everywhere else in the app without a second input styling system.
 */
import { useEffect, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { MapCanvas } from './MapCanvas';
import { Input } from '@/components/ui';

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
  const inputRef = useRef<HTMLInputElement>(null);
  const mapRef = useRef<google.maps.Map | null>(null);
  const markerRef = useRef<google.maps.Marker | null>(null);
  const mapsRef = useRef<typeof google.maps | null>(null);
  const [address, setAddress] = useState(value?.address ?? '');

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
      const addr = status === 'OK' && results?.[0] ? results[0].formatted_address : address;
      setAddress(addr);
      onChange({ address: addr, lat, lon, place_id: results?.[0]?.place_id ?? null });
    });
  };

  useEffect(() => {
    if (!mapsRef.current || !inputRef.current) return;
    const maps = mapsRef.current;
    const autocomplete = new maps.places.Autocomplete(inputRef.current, {
      fields: ['formatted_address', 'geometry', 'place_id', 'name'],
    });
    const listener = autocomplete.addListener('place_changed', () => {
      const place = autocomplete.getPlace();
      const loc = place.geometry?.location;
      if (!loc || !mapRef.current) return;
      const lat = loc.lat();
      const lon = loc.lng();
      const addr = place.formatted_address ?? place.name ?? '';
      setAddress(addr);
      onChange({ address: addr, lat, lon, place_id: place.place_id ?? null });
      placeAt(maps, mapRef.current, lat, lon);
    });
    return () => listener.remove();
    // Re-bind only when the map instance itself changes (first ready call).
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [mapRef.current]);

  return (
    <div className="space-y-2">
      <Input
        ref={inputRef} id={id} value={address} placeholder={placeholder}
        onChange={(e) => setAddress(e.target.value)}
      />
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
        }}
      />
    </div>
  );
}
