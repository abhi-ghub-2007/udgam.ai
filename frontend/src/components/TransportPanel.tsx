/**
 * F-7: arranging transport for an order, and seeing where that has got to.
 *
 * The panel answers one question at a time, in the order the work actually
 * happens: who is arranging it, where is it going from and to, who could carry
 * it, and then — the state people most often have to guess at — what are we
 * waiting for. Every pending state here says what it is waiting on and who is
 * expected to act, because "Waiting for a transporter to accept" is a very
 * different feeling from a spinner.
 *
 * Only the party named by `logistics_arranged_by` gets the controls. The other
 * side sees the same facts read-only, so a buyer can watch a farmer's
 * arrangements without being able to change them under their feet — which the
 * server enforces regardless.
 */
import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import {
  useSaveShipmentDetails, useSendTransportOffers, useTransportOptions,
} from '@/hooks/queries';
import { LocationPicker, type PickedLocation } from '@/components/maps/LocationPicker';
import { ApiError } from '@/services/api/client';
import {
  Badge, Button, Card, CardTitle, EmptyState, Field, Input, Textarea, cx,
} from '@/components/ui';
import { money, number, date } from '@/utils/format';
import type { Order, ShipmentDetails, TransportOption } from '@/types/api';

interface Props {
  order: Order;
  shipment: ShipmentDetails | null;
  /** True when the viewer is the party named by logistics_arranged_by. */
  canArrange: boolean;
}

function Stars({ value, count }: { value: number | null; count: number }) {
  const { t } = useTranslation();
  if (!count) return <span className="text-label text-ink-muted">{t('review.none')}</span>;
  return (
    <span className="text-label text-ink-muted">
      <span aria-hidden>★</span> <span className="tnum">{value?.toFixed(1)}</span>
      {' '}({count})
    </span>
  );
}

function OptionRow({ option, selected, onToggle, disabled }: {
  option: TransportOption; selected: boolean; onToggle: () => void; disabled: boolean;
}) {
  const { t } = useTranslation();
  const asked = option.offer_status === 'pending';
  return (
    <li>
      <label
        className={cx(
          'flex cursor-pointer flex-wrap items-center gap-3 rounded-md border-card p-3 transition-colors duration-fast',
          selected ? 'border-primary bg-primary-container/30' : 'border-outline-variant hover:bg-surface-low',
          (asked || disabled) && 'cursor-not-allowed opacity-60',
        )}
      >
        <input
          type="checkbox" className="sr-only" checked={selected}
          disabled={asked || disabled} onChange={onToggle}
        />
        <span aria-hidden className={cx(
          'h-4 w-4 shrink-0 rounded-sm border-card',
          selected ? 'border-primary bg-primary' : 'border-outline-variant',
        )} />
        <span className="min-w-0 flex-1">
          <span className="block text-body font-semibold text-ink">
            {option.transporter_name ?? t('nav.transport')}
          </span>
          <span className="block text-label text-ink-muted">
            {[option.origin_district, option.dest_district].filter(Boolean).join(' → ')}
            {option.route_km != null && ` · ${number(option.route_km)} km`}
            {' · '}{t('market.free_capacity')} {number(option.available_capacity_kg)} {t('common.kg')}
          </span>
          {/* Shown to inform the choice. It is not what ordered this list. */}
          <Stars value={option.reliability.avg_rating} count={option.reliability.rating_count} />
        </span>
        <span className="text-right">
          <span className="tnum block text-body font-semibold text-primary">
            {money(option.estimated_cost_paise)}
          </span>
          {asked && <Badge tone="info">{t('market.requested')}</Badge>}
        </span>
      </label>
    </li>
  );
}

export function TransportPanel({ order, shipment, canArrange }: Props) {
  const { t } = useTranslation();
  const save = useSaveShipmentDetails(order.id);
  const sendOffers = useSendTransportOffers(order.id);
  const hasDetails = Boolean(shipment?.pickup_address && shipment?.drop_address);
  const assigned = Boolean(shipment?.transporter_id);
  const options = useTransportOptions(order.id, canArrange && hasDetails && !assigned);

  const [editing, setEditing] = useState(false);
  const [picked, setPicked] = useState<string[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [form, setForm] = useState({
    pickup_contact_name: shipment?.pickup_contact_name ?? '',
    pickup_contact_phone: shipment?.pickup_contact_phone ?? '',
    pickup_from: shipment?.pickup_from?.slice(0, 16) ?? '',
    pickup_until: shipment?.pickup_until?.slice(0, 16) ?? '',
    pickup_instructions: shipment?.pickup_instructions ?? '',
    drop_contact_name: shipment?.drop_contact_name ?? '',
    drop_contact_phone: shipment?.drop_contact_phone ?? '',
    deliver_by: shipment?.deliver_by?.slice(0, 16) ?? '',
    drop_instructions: shipment?.drop_instructions ?? '',
    transport_paid_by: shipment?.transport_paid_by ?? order.logistics_arranged_by ?? 'buyer',
  });
  // Selected via Google Places (§5) -- address alone, the previous design,
  // gave route/distance/tracking/geofencing nothing to compute from.
  const [pickupLoc, setPickupLoc] = useState<PickedLocation | null>(
    shipment?.pickup_address
      ? { address: shipment.pickup_address, lat: shipment.pickup_lat ?? 0,
          lon: shipment.pickup_lon ?? 0, place_id: shipment.pickup_place_id }
      : null,
  );
  const [dropLoc, setDropLoc] = useState<PickedLocation | null>(
    shipment?.drop_address
      ? { address: shipment.drop_address, lat: shipment.drop_lat ?? 0,
          lon: shipment.drop_lon ?? 0, place_id: shipment.drop_place_id }
      : null,
  );

  const set = (k: keyof typeof form) => (v: string) =>
    setForm((p) => ({ ...p, [k]: v }));

  const iso = (v: string) => (v ? new Date(v).toISOString() : null);

  const onSave = async () => {
    setError(null);
    if (!pickupLoc || !dropLoc) {
      setError(t('market.err_pickup_drop_required'));
      return;
    }
    try {
      await save.mutateAsync({
        ...form,
        pickup_address: pickupLoc.address, pickup_lat: pickupLoc.lat,
        pickup_lon: pickupLoc.lon, pickup_place_id: pickupLoc.place_id,
        drop_address: dropLoc.address, drop_lat: dropLoc.lat,
        drop_lon: dropLoc.lon, drop_place_id: dropLoc.place_id,
        pickup_from: iso(form.pickup_from),
        pickup_until: iso(form.pickup_until),
        deliver_by: iso(form.deliver_by),
      });
      setEditing(false);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : t('common.error_body'));
    }
  };

  const onSend = async () => {
    setError(null);
    try {
      await sendOffers.mutateAsync(picked);
      setPicked([]);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : t('common.error_body'));
    }
  };

  const pendingCount = (options.data?.options ?? [])
    .filter((o) => o.offer_status === 'pending').length;

  return (
    <Card className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <CardTitle>{t('market.arrange_transport')}</CardTitle>
        <Badge tone="neutral">
          {t('market.who_arranges')}: {t(`market.party_${order.logistics_arranged_by}`)}
        </Badge>
      </div>

      {error && (
        <p role="alert" className="rounded-md bg-danger-container px-3 py-2 text-body text-danger-on-container">
          {error}
        </p>
      )}

      {/* ---- the facts, once they exist ---- */}
      {hasDetails && !editing && (
        <dl className="grid gap-4 sm:grid-cols-2">
          <div>
            <dt className="text-label text-ink-muted">{t('transporter.pickup')}</dt>
            <dd className="text-body font-semibold text-ink">{shipment?.pickup_address}</dd>
            {shipment?.pickup_from && (
              <dd className="tnum text-label text-ink-muted">
                {date(shipment.pickup_from)}
                {shipment.pickup_until && ` – ${date(shipment.pickup_until)}`}
              </dd>
            )}
          </div>
          <div>
            <dt className="text-label text-ink-muted">{t('transporter.drop')}</dt>
            <dd className="text-body font-semibold text-ink">{shipment?.drop_address}</dd>
            {shipment?.deliver_by && (
              <dd className="tnum text-label text-ink-muted">
                {t('market.deliver_by')} {date(shipment.deliver_by)}
              </dd>
            )}
          </div>
          {shipment?.transport_paid_by && (
            <div>
              <dt className="text-label text-ink-muted">{t('market.who_pays')}</dt>
              <dd className="text-body font-semibold text-ink">
                {t(`market.party_${shipment.transport_paid_by}`)}
              </dd>
            </div>
          )}
          {shipment?.transport_cost_estimate_paise != null && (
            <div>
              <dt className="text-label text-ink-muted">{t('market.estimated_cost')}</dt>
              <dd className="tnum text-body font-semibold text-ink">
                {money(shipment.transport_cost_estimate_paise)}
              </dd>
            </div>
          )}
        </dl>
      )}

      {/* ---- what are we waiting for ---- */}
      {assigned ? (
        <Badge tone="success">{t('market.transport_assigned')}</Badge>
      ) : hasDetails && pendingCount > 0 ? (
        <div className="rounded-md bg-surface-low px-3 py-2">
          <p className="text-body font-semibold text-ink">{t('market.awaiting_transporter')}</p>
          <p className="text-label text-ink-muted">
            {t('market.awaiting_transporter_body', { n: pendingCount })}
          </p>
        </div>
      ) : null}

      {!canArrange && (
        <p className="text-label text-ink-muted">
          {t('market.who_arranges')}: {t(`market.party_${order.logistics_arranged_by}`)}
        </p>
      )}

      {/* ---- the arranger's controls ---- */}
      {canArrange && !assigned && (editing || !hasDetails) && (
        <div className="space-y-4 border-t border-line-card pt-4">
          <Field label={t('market.pickup_address')} htmlFor="pk-addr" required>
            <LocationPicker
              id="pk-addr" value={pickupLoc} onChange={setPickupLoc}
              placeholder={t('maps.search_hint')}
            />
          </Field>
          <div className="grid gap-4 sm:grid-cols-2">
            <Field label={t('market.contact_name')} htmlFor="pk-name">
              <Input id="pk-name" value={form.pickup_contact_name}
                     onChange={(e) => set('pickup_contact_name')(e.target.value)} />
            </Field>
            <Field label={t('market.contact_phone')} htmlFor="pk-phone">
              <Input id="pk-phone" inputMode="tel" value={form.pickup_contact_phone}
                     onChange={(e) => set('pickup_contact_phone')(e.target.value)} />
            </Field>
            <Field label={`${t('market.pickup_window')} — ${t('market.window_from')}`} htmlFor="pk-from">
              <Input id="pk-from" type="datetime-local" value={form.pickup_from}
                     onChange={(e) => set('pickup_from')(e.target.value)} />
            </Field>
            <Field label={`${t('market.pickup_window')} — ${t('market.window_until')}`} htmlFor="pk-until">
              <Input id="pk-until" type="datetime-local" value={form.pickup_until}
                     onChange={(e) => set('pickup_until')(e.target.value)} />
            </Field>
          </div>
          <Field label={t('market.loading_notes')} htmlFor="pk-notes">
            <Textarea id="pk-notes" maxLength={500} value={form.pickup_instructions}
                      onChange={(e) => set('pickup_instructions')(e.target.value)} />
          </Field>

          <Field label={t('market.drop_address')} htmlFor="dp-addr" required>
            <LocationPicker
              id="dp-addr" value={dropLoc} onChange={setDropLoc}
              placeholder={t('maps.search_hint')}
            />
          </Field>
          <div className="grid gap-4 sm:grid-cols-2">
            <Field label={t('market.contact_name')} htmlFor="dp-name">
              <Input id="dp-name" value={form.drop_contact_name}
                     onChange={(e) => set('drop_contact_name')(e.target.value)} />
            </Field>
            <Field label={t('market.contact_phone')} htmlFor="dp-phone">
              <Input id="dp-phone" inputMode="tel" value={form.drop_contact_phone}
                     onChange={(e) => set('drop_contact_phone')(e.target.value)} />
            </Field>
            <Field label={t('market.deliver_by')} htmlFor="dp-by">
              <Input id="dp-by" type="datetime-local" value={form.deliver_by}
                     onChange={(e) => set('deliver_by')(e.target.value)} />
            </Field>
            <Field label={t('market.who_pays')} htmlFor="paid-by" hint={t('market.who_pays_hint')}>
              <select
                id="paid-by" value={form.transport_paid_by}
                onChange={(e) => set('transport_paid_by')(e.target.value)}
                className="min-h-tap w-full rounded-md border-card border-outline-variant bg-surface px-3 text-body text-ink"
              >
                <option value="farmer">{t('market.party_farmer')}</option>
                <option value="buyer">{t('market.party_buyer')}</option>
              </select>
            </Field>
          </div>
          <Field label={t('market.unloading_notes')} htmlFor="dp-notes">
            <Textarea id="dp-notes" maxLength={500} value={form.drop_instructions}
                      onChange={(e) => set('drop_instructions')(e.target.value)} />
          </Field>

          <div className="flex flex-wrap gap-3">
            <Button loading={save.isPending} onClick={() => void onSave()}>
              {t('market.save_transport_details')}
            </Button>
            {hasDetails && (
              <Button variant="outline" onClick={() => setEditing(false)}>{t('common.cancel')}</Button>
            )}
          </div>
        </div>
      )}

      {canArrange && hasDetails && !assigned && !editing && (
        <Button variant="outline" onClick={() => setEditing(true)}>
          {t('market.transport_details')}
        </Button>
      )}

      {/* ---- carriers ---- */}
      {canArrange && hasDetails && !assigned && (
        <div className="space-y-3 border-t border-line-card pt-4">
          <CardTitle className="text-body">{t('market.transport_options_title')}</CardTitle>
          {options.isLoading ? (
            <p className="text-body text-ink-muted">{t('common.loading')}</p>
          ) : (options.data?.options.length ?? 0) === 0 ? (
            <EmptyState title={t('market.no_options')} body={t('market.no_options_body')} />
          ) : (
            <>
              <ul className="space-y-2">
                {options.data?.options.map((o) => (
                  <OptionRow
                    key={o.capacity_id} option={o}
                    selected={picked.includes(o.capacity_id)}
                    disabled={sendOffers.isPending}
                    onToggle={() => setPicked((p) => p.includes(o.capacity_id)
                      ? p.filter((x) => x !== o.capacity_id)
                      : [...p, o.capacity_id])}
                  />
                ))}
              </ul>
              {/* Says out loud what the list is ordered by, and what it is not. */}
              <p className="text-label text-ink-muted">{t('market.ranked_note')}</p>
              <Button
                loading={sendOffers.isPending} disabled={picked.length === 0}
                onClick={() => void onSend()}
              >
                {t('market.request_selected')}
                {picked.length > 0 && ` (${picked.length})`}
              </Button>
            </>
          )}
        </div>
      )}
    </Card>
  );
}
