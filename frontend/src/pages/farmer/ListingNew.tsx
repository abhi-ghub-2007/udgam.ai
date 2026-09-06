/**
 * Create a listing.
 *
 * Money is entered in RUPEES (what a farmer thinks in) and converted to
 * integer paise at the boundary, because the backend contract is paise
 * end-to-end. That conversion happens once, here, and nowhere else.
 */
import { useState, type FormEvent } from 'react';
import { useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { useCreateListing, useCrops } from '@/hooks/queries';
import { useAuth } from '@/services/auth/AuthProvider';
import { ApiError } from '@/services/api/client';
import { Button, Card, Field, Input, PageHeader, Select, Textarea } from '@/components/ui';

export default function ListingNew() {
  const { t, i18n } = useTranslation();
  const navigate = useNavigate();
  const { profile } = useAuth();
  const crops = useCrops();
  const create = useCreateListing();

  const [f, setF] = useState({
    crop_id: '', quantity_kg: '', price_rupees: '',
    harvest_date: '', available_until: '', district: profile?.district ?? '', description: '',
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
    const price = Number(f.price_rupees);
    if (!(price > 0)) errs.price_rupees = t('market.err_price');
    setErrors(errs);
    if (Object.keys(errs).length) return;

    try {
      await create.mutateAsync({
        crop_id: f.crop_id,
        quantity_kg: qty,
        // Rupees -> integer paise. The only place this conversion happens.
        asking_price_paise: Math.round(price * 100),
        harvest_date: f.harvest_date || null,
        available_until: f.available_until || null,
        district: f.district.trim() || null,
        description: f.description.trim() || null,
      });
      navigate('/farmer/listings', { replace: true });
    } catch (err) {
      setErrors({ form: err instanceof ApiError ? err.message : t('common.error_body') });
    }
  };

  return (
    <div className="space-y-6">
      <PageHeader title={t('market.new_listing_title')} />
      <Card className="max-w-2xl">
        <form onSubmit={onSubmit} noValidate className="space-y-4">
          {errors.form && (
            <p role="alert" className="rounded-md bg-danger-container px-3 py-2 text-body text-danger-on-container">
              {errors.form}
            </p>
          )}

          <Field label={t('market.crop')} htmlFor="crop" error={errors.crop_id} required>
            <Select id="crop" value={f.crop_id} onChange={(e) => set('crop_id')(e.target.value)}
                    invalid={Boolean(errors.crop_id)} disabled={crops.isLoading}>
              <option value="">{crops.isLoading ? t('common.loading') : '—'}</option>
              {(crops.data ?? []).map((c) => (
                <option key={c.id} value={c.id}>{cropName(c)}</option>
              ))}
            </Select>
          </Field>

          <div className="grid gap-4 sm:grid-cols-2">
            <Field label={t('market.quantity_kg')} htmlFor="qty" error={errors.quantity_kg} required>
              <Input id="qty" type="number" inputMode="decimal" min="0" step="0.01"
                     value={f.quantity_kg} invalid={Boolean(errors.quantity_kg)}
                     onChange={(e) => set('quantity_kg')(e.target.value)} />
            </Field>
            <Field label={t('market.price_per_kg')} htmlFor="price" error={errors.price_rupees} required>
              <Input id="price" type="number" inputMode="decimal" min="0" step="0.01"
                     value={f.price_rupees} invalid={Boolean(errors.price_rupees)}
                     onChange={(e) => set('price_rupees')(e.target.value)} />
            </Field>
          </div>

          <div className="grid gap-4 sm:grid-cols-2">
            <Field label={t('market.harvest_date')} htmlFor="harvest">
              <Input id="harvest" type="date" value={f.harvest_date}
                     onChange={(e) => set('harvest_date')(e.target.value)} />
            </Field>
            <Field label={t('market.available_until')} htmlFor="until">
              <Input id="until" type="date" value={f.available_until}
                     onChange={(e) => set('available_until')(e.target.value)} />
            </Field>
          </div>

          <Field label={t('auth.district')} htmlFor="district" hint={t('market.district_hint')}>
            <Input id="district" value={f.district} onChange={(e) => set('district')(e.target.value)} />
          </Field>

          <Field label={t('market.description')} htmlFor="desc">
            <Textarea id="desc" maxLength={1000} value={f.description}
                      onChange={(e) => set('description')(e.target.value)} />
          </Field>

          <div className="flex flex-wrap gap-3">
            <Button type="submit" loading={create.isPending}>{t('market.list_new')}</Button>
            <Button type="button" variant="outline" onClick={() => navigate(-1)}>
              {t('common.cancel')}
            </Button>
          </div>
        </form>
      </Card>
    </div>
  );
}
