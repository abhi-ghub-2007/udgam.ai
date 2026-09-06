/**
 * Live shipment updates over Supabase Realtime (§9/§10/§22).
 *
 * This is the actual "our app tracks the transporter" half of the design the
 * spec is explicit about: browser geolocation -> our backend -> Postgres ->
 * Realtime -> this subscription -> the map marker. Google Maps never learns
 * the transporter's position from this; it only ever renders it.
 *
 * `shipments` was added to the `supabase_realtime` publication in SCHEMA.sql,
 * and RLS keeps applying to the changefeed -- an unauthorised viewer's
 * subscription simply never receives events for a row shipments_select would
 * not let them SELECT.
 *
 * Deliberately not a second polling loop: TanStack Query already owns
 * `['shipments']`, so a realtime event just patches that cache in place
 * (setQueryData), never a full refetch and never a page reload.
 */
import { useEffect, useRef } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { getSupabase } from '@/services/supabase/client';
import type { Shipment } from '@/types/api';

type ConnectionState = 'connecting' | 'connected' | 'disconnected';

export function useShipmentRealtime(
  shipmentId: string | undefined,
  onUpdate?: (row: Partial<Shipment>) => void,
  onStateChange?: (state: ConnectionState) => void,
) {
  const qc = useQueryClient();
  const onUpdateRef = useRef(onUpdate);
  onUpdateRef.current = onUpdate;
  const onStateRef = useRef(onStateChange);
  onStateRef.current = onStateChange;

  useEffect(() => {
    if (!shipmentId) return undefined;

    let supabase;
    try {
      supabase = getSupabase();
    } catch {
      // Supabase not configured in this deployment -- the caller's UI
      // already handles a tracking page with no live updates; nothing here
      // should throw past that.
      return undefined;
    }

    onStateRef.current?.('connecting');
    const channel = supabase
      .channel(`shipment:${shipmentId}`)
      .on(
        'postgres_changes',
        { event: 'UPDATE', schema: 'public', table: 'shipments', filter: `id=eq.${shipmentId}` },
        (payload) => {
          const row = payload.new as Partial<Shipment>;
          qc.setQueryData(['shipments', 'live', shipmentId], row);
          onUpdateRef.current?.(row);
        },
      )
      .subscribe((status) => {
        if (status === 'SUBSCRIBED') onStateRef.current?.('connected');
        else if (status === 'CHANNEL_ERROR' || status === 'TIMED_OUT' || status === 'CLOSED') {
          onStateRef.current?.('disconnected');
        }
      });

    return () => {
      void supabase.removeChannel(channel);
    };
  }, [shipmentId, qc]);
}
