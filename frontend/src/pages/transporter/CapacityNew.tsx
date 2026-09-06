import { useState, type FormEvent } from 'react';
import { useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { usePostCapacity } from '@/hooks/queries';
import { useAuth } from '@/services/auth/AuthProvider';
import { ApiError } from '@/services/api/client';
import { Button, Card, Field, Input, PageHeader, Select } from '@/components/ui';

/** Matches the capacity_type enum in db/SCHEMA.sql exactly. */
const TYPES = ['scheduled_route', 'empty_leg', 'on_demand'] as const;

export default function CapacityNew() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const { profile } = useAuth();
  const post = usePostCapacity();

  const [f, setF] = useState({
    capacity_type: 'scheduled_route' as (typeof TYPES)[number],
    origin_district: profile?.district ?? '',
    dest_district: '',
    depart_at: '',
    total_capacity_kg: '',
    price_rupees_per_kg: '',
    discount_pct: '0',
  });
  const [errors, setErrors] = useState<Record<string, string | undefined>>({});

  const set = (k: keyof typeof f) => (v: string) => {
    setF((p) => ({ ...p, [k]: v }));
    setErrors((p) => ({ ...p, [k]: undefined, form: undefined }));
  };

  const onSubmit = async (e: FormEvent) => {
    e.preventDefault();
    const errs: Record<string, string> = {};
    const cap = Number(f.total_capacity_kg);
    if (!(cap > 0)) errs.total_capacity_kg = t('market.err_quantity');
    setErrors(errs);
    if (Object.keys(errs).length) return;

    const price = Number(f.price_rupees_per_kg);
    try {
      await post.mutateAsync({
        capacity_type: f.capacity_type,
        origin_district: f.origin_district.trim() || null,
        dest_district: f.dest_district.trim() || null,
        // datetime-local has no zone; send it as-is and let the backend store it.
        depart_at: f.depart_at ? new Date(f.depart_at).toISOString() : null,
        total_capacity_kg: cap,
        price_paise_per_kg: price > 0 ? Math.round(price * 100) : 0,
        discount_pct: Number(f.discount_pct) || 0,
      });
      navigate('/transporter/capacity', { replace: true });
    } catch (err) {
      setErrors({ form: err instanceof ApiError ? err.message : t('common.error_body') });
    }
  };

  return (
    <div className="space-y-6">
      <PageHeader title={t('transporter.route_plan')} />
      <Card className="max-w-2xl">
        <form onSubmit={onSubmit} noValidate className="space-y-4">
          {errors.form && (
            <p role="alert" className="rounded-md bg-danger-container px-3 py-2 text-body text-danger-on-container">
              {errors.form}
            </p>
          )}

          <Field label={t('transporter.route_plan')} htmlFor="c-type" required>
            <Select id="c-type" value={f.capacity_type}
                    onChange={(e) => set('capacity_type')(e.target.value)}>
              {TYPES.map((ty) => (
                <option key={ty} value={ty}>{t(`transporter.capacity_type.${ty}`)}</option>
              ))}
            </Select>
          </Field>

          <div className="grid gap-4 sm:grid-cols-2">
            <Field label={t('transporter.pickup_pincode')} htmlFor="c-from">
              <Input id="c-from" value={f.origin_district}
                     onChange={(e) => set('origin_district')(e.target.value)} />
            </Field>
            <Field label={t('transporter.drop_pincode')} htmlFor="c-to">
              <Input id="c-to" value={f.dest_district}
                     onChange={(e) => set('dest_district')(e.target.value)} />
            </Field>
          </div>

          <div className="grid gap-4 sm:grid-cols-2">
            <Field label={t('market.quantity_kg')} htmlFor="c-cap"
                   error={errors.total_capacity_kg} required>
              <Input id="c-cap" type="number" inputMode="decimal" min="0" step="0.01"
                     value={f.total_capacity_kg} invalid={Boolean(errors.total_capacity_kg)}
                     onChange={(e) => set('total_capacity_kg')(e.target.value)} />
            </Field>
            <Field label={t('market.price_per_kg')} htmlFor="c-price">
              <Input id="c-price" type="number" inputMode="decimal" min="0" step="0.01"
                     value={f.price_rupees_per_kg}
                     onChange={(e) => set('price_rupees_per_kg')(e.target.value)} />
            </Field>
          </div>

          <div className="grid gap-4 sm:grid-cols-2">
            <Field label={t('market.needed_by')} htmlFor="c-depart">
              <Input id="c-depart" type="datetime-local" value={f.depart_at}
                     onChange={(e) => set('depart_at')(e.target.value)} />
            </Field>
            <Field label="%" htmlFor="c-disc">
              <Input id="c-disc" type="number" min="0" max="100" step="1"
                     value={f.discount_pct} onChange={(e) => set('discount_pct')(e.target.value)} />
            </Field>
          </div>

          <div className="flex flex-wrap gap-3">
            <Button type="submit" loading={post.isPending}>{t('common.save')}</Button>
            <Button type="button" variant="outline" onClick={() => navigate(-1)}>
              {t('common.cancel')}
            </Button>
          </div>
        </form>
      </Card>
    </div>
  );
}
