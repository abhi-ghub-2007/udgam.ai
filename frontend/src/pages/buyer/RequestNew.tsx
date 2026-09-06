import { useState, type FormEvent } from 'react';
import { useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { useCreateRequest, useCrops } from '@/hooks/queries';
import { useAuth } from '@/services/auth/AuthProvider';
import { ApiError } from '@/services/api/client';
import { Button, Card, Field, Input, PageHeader, Select, Textarea } from '@/components/ui';

export default function RequestNew() {
  const { t, i18n } = useTranslation();
  const navigate = useNavigate();
  const { profile } = useAuth();
  const crops = useCrops();
  const create = useCreateRequest();

  const [f, setF] = useState({
    crop_id: '', quantity_kg: '', min_grade: 'C', target_rupees: '',
    needed_by: '', delivery_district: profile?.district ?? '',
    delivery_pincode: profile?.pincode ?? '', notes: '',
  });
  const [errors, setErrors] = useState<Record<string, string | undefined>>({});

  const set = (k: keyof typeof f) => (v: string) => {
    setF((p) => ({ ...p, [k]: v }));
    setErrors((p) => ({ ...p, [k]: undefined, form: undefined }));
  };

  const cropName = (c: { name_en: string; name_hi: string; name_mr: string }) =>
    i18n.language === 'hi' ? c.name_hi : i18n.language === 'mr' ? c.name_mr : c.name_en;

  const onSubmit = async (e: FormEvent) => {
    e.preventDefault();
    const errs: Record<string, string> = {};
    if (!f.crop_id) errs.crop_id = t('market.err_crop');
    const qty = Number(f.quantity_kg);
    if (!(qty > 0)) errs.quantity_kg = t('market.err_quantity');
    setErrors(errs);
    if (Object.keys(errs).length) return;

    const target = Number(f.target_rupees);
    try {
      await create.mutateAsync({
        crop_id: f.crop_id,
        quantity_kg: qty,
        min_grade: f.min_grade,
        // Rupees -> integer paise, at the boundary only.
        target_price_paise: target > 0 ? Math.round(target * 100) : null,
        needed_by: f.needed_by || null,
        delivery_district: f.delivery_district.trim() || null,
        delivery_pincode: f.delivery_pincode.trim() || null,
        notes: f.notes.trim() || null,
      });
      navigate('/buyer/requests', { replace: true });
    } catch (err) {
      setErrors({ form: err instanceof ApiError ? err.message : t('common.error_body') });
    }
  };

  return (
    <div className="space-y-6">
      <PageHeader title={t('buyer.post_requirement')} />
      <Card className="max-w-2xl">
        <form onSubmit={onSubmit} noValidate className="space-y-4">
          {errors.form && (
            <p role="alert" className="rounded-md bg-danger-container px-3 py-2 text-body text-danger-on-container">
              {errors.form}
            </p>
          )}

          <Field label={t('market.crop')} htmlFor="r-crop" error={errors.crop_id} required>
            <Select id="r-crop" value={f.crop_id} invalid={Boolean(errors.crop_id)}
                    onChange={(e) => set('crop_id')(e.target.value)} disabled={crops.isLoading}>
              <option value="">{crops.isLoading ? t('common.loading') : '—'}</option>
              {(crops.data ?? []).map((c) => (
                <option key={c.id} value={c.id}>{cropName(c)}</option>
              ))}
            </Select>
          </Field>

          <div className="grid gap-4 sm:grid-cols-2">
            <Field label={t('market.quantity_kg')} htmlFor="r-qty" error={errors.quantity_kg} required>
              <Input id="r-qty" type="number" inputMode="decimal" min="0" step="0.01"
                     value={f.quantity_kg} invalid={Boolean(errors.quantity_kg)}
                     onChange={(e) => set('quantity_kg')(e.target.value)} />
            </Field>
            <Field label={t('market.target_price')} htmlFor="r-price">
              <Input id="r-price" type="number" inputMode="decimal" min="0" step="0.01"
                     value={f.target_rupees} onChange={(e) => set('target_rupees')(e.target.value)} />
            </Field>
          </div>

          <div className="grid gap-4 sm:grid-cols-2">
            <Field label={t('market.min_grade')} htmlFor="r-grade">
              <Select id="r-grade" value={f.min_grade} onChange={(e) => set('min_grade')(e.target.value)}>
                {['A', 'B', 'C'].map((g) => <option key={g} value={g}>{g}</option>)}
              </Select>
            </Field>
            <Field label={t('market.needed_by')} htmlFor="r-needed">
              <Input id="r-needed" type="date" value={f.needed_by}
                     onChange={(e) => set('needed_by')(e.target.value)} />
            </Field>
          </div>

          <div className="grid gap-4 sm:grid-cols-2">
            <Field label={t('auth.district')} htmlFor="r-district">
              <Input id="r-district" value={f.delivery_district}
                     onChange={(e) => set('delivery_district')(e.target.value)} />
            </Field>
            <Field label={t('auth.pincode')} htmlFor="r-pin">
              <Input id="r-pin" inputMode="numeric" value={f.delivery_pincode}
                     onChange={(e) => set('delivery_pincode')(e.target.value)} />
            </Field>
          </div>

          <Field label={t('market.description')} htmlFor="r-notes">
            <Textarea id="r-notes" value={f.notes} onChange={(e) => set('notes')(e.target.value)} />
          </Field>

          <div className="flex flex-wrap gap-3">
            <Button type="submit" loading={create.isPending}>{t('buyer.post_requirement')}</Button>
            <Button type="button" variant="outline" onClick={() => navigate(-1)}>
              {t('common.cancel')}
            </Button>
          </div>
        </form>
      </Card>
    </div>
  );
}
