/**
 * Create a listing, then grade it from a photo (F-2 / AI-1).
 *
 * Two real backend calls, in order:
 *   POST /api/products              -> creates the listing
 *   POST /api/products/{id}/photo   -> runs AI-1 server-side, returns the grade
 * The grade is never computed in the browser. The farmer sees the result and
 * explicitly confirms before leaving the flow (PRD 1D) -- this is the
 * feature the React migration dropped and this file restores.
 *
 * Money is entered in RUPEES (what a farmer thinks in) and converted to
 * integer paise at the boundary, because the backend contract is paise
 * end-to-end. That conversion happens once, here, and nowhere else.
 */
import { useRef, useState, type FormEvent } from 'react';
import { useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { useCreateListing, useCrops, useGradePhoto } from '@/hooks/queries';
import { useAuth } from '@/services/auth/AuthProvider';
import { ApiError } from '@/services/api/client';
import { Button, Card, Field, Input, PageHeader, Select, Textarea } from '@/components/ui';
import { GradeResultPanel } from '@/components/GradeResultPanel';
import type { GradeResult, Product } from '@/types/api';

/** Three shots, each with a stated purpose, so the farmer knows what to take.
    Matches the legacy SHOTS list exactly -- same i18n keys, same order. */
const SHOTS = [
  { id: 'shot-batch', key: 'market.shot_batch' },
  { id: 'shot-size', key: 'market.shot_size' },
  { id: 'shot-quality', key: 'market.shot_quality' },
] as const;

export default function ListingNew() {
  const { t, i18n } = useTranslation();
  const navigate = useNavigate();
  const { profile } = useAuth();
  const crops = useCrops();
  const create = useCreateListing();
  const gradePhoto = useGradePhoto();

  const [f, setF] = useState({
    crop_id: '', quantity_kg: '', price_rupees: '',
    harvest_date: '', available_until: '', district: profile?.district ?? '', description: '',
  });
  const [errors, setErrors] = useState<Record<string, string | undefined>>({});
  const [previews, setPreviews] = useState<Record<string, string>>({});
  const fileInputs = useRef<Record<string, HTMLInputElement | null>>({});

  // Post-create state: once the listing exists, the form gives way to the
  // grading step, then to the result panel -- exactly the legacy sequence.
  const [created, setCreated] = useState<Product | null>(null);
  const [grading, setGrading] = useState(false);
  const [gradeError, setGradeError] = useState<string | null>(null);
  const [gradeResult, setGradeResult] = useState<GradeResult | null>(null);

  const set = (k: keyof typeof f) => (v: string) => {
    setF((p) => ({ ...p, [k]: v }));
    setErrors((p) => ({ ...p, [k]: undefined, form: undefined }));
  };

  const cropName = (c: { name_en: string; name_hi: string; name_mr: string }) =>
    i18n.language === 'hi' ? c.name_hi : i18n.language === 'mr' ? c.name_mr : c.name_en;

  const onFileChange = (shotId: string) => (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    const url = URL.createObjectURL(file);
    setPreviews((p) => {
      const old = p[shotId];
      if (old) URL.revokeObjectURL(old);
      return { ...p, [shotId]: url };
    });
  };

  /** The first photo actually selected, across the three slots -- only one is
      graded, matching the legacy behaviour exactly. */
  const firstSelectedFile = (): File | null => {
    for (const s of SHOTS) {
      const file = fileInputs.current[s.id]?.files?.[0];
      if (file) return file;
    }
    return null;
  };

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

    let product: Product;
    try {
      product = await create.mutateAsync({
        crop_id: f.crop_id,
        quantity_kg: qty,
        // Rupees -> integer paise. The only place this conversion happens.
        asking_price_paise: Math.round(price * 100),
        harvest_date: f.harvest_date || null,
        available_until: f.available_until || null,
        district: f.district.trim() || null,
        description: f.description.trim() || null,
      });
    } catch (err) {
      setErrors({ form: err instanceof ApiError ? err.message : t('common.error_body') });
      return;
    }

    const photo = firstSelectedFile();
    if (!photo) {
      // No photo picked: the listing stands ungraded, exactly as the legacy
      // flow allowed -- grading is offered, never forced.
      navigate(`/farmer/listings/${product.id}`, { replace: true });
      return;
    }

    setCreated(product);
    setGrading(true);
    setGradeError(null);
    try {
      const grade = await gradePhoto.mutateAsync({ productId: product.id, file: photo });
      setGradeResult(grade);
    } catch (err) {
      // The listing already exists and is live -- a failed grade must not
      // strand the farmer. They can still go view the (ungraded) listing.
      setGradeError(err instanceof ApiError ? err.message : t('common.error_body'));
    } finally {
      setGrading(false);
    }
  };

  // ---- step 2: grading in progress or the result panel ------------------
  if (created) {
    return (
      <div className="space-y-6">
        <PageHeader title={t('market.new_listing_title')} />
        <div className="max-w-2xl space-y-4">
          {grading && (
            <Card className="animate-pulse text-body text-ink-muted">{t('market.grading')}</Card>
          )}
          {gradeError && (
            <Card className="space-y-3 border-danger/30">
              <p role="alert" className="text-body text-danger">{gradeError}</p>
              <Button variant="outline" onClick={() => navigate(`/farmer/listings/${created.id}`, { replace: true })}>
                {t('common.back')}
              </Button>
            </Card>
          )}
          {gradeResult && (
            <GradeResultPanel
              grade={gradeResult}
              onConfirm={() => navigate(`/farmer/listings/${created.id}`, { replace: true })}
            />
          )}
        </div>
      </div>
    );
  }

  // ---- step 1: the listing form ------------------------------------------
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

          {/* AI-1: photo -> quality grade. Optional -- the listing publishes
              either way -- but offered up front, in the same form. */}
          <fieldset className="space-y-2 border-0 p-0">
            <legend className="text-label font-semibold text-ink">{t('market.photos')}</legend>
            <div className="grid grid-cols-3 gap-3">
              {SHOTS.map((s) => (
                <label
                  key={s.id}
                  htmlFor={s.id}
                  className="flex aspect-square cursor-pointer flex-col items-center justify-center gap-1 overflow-hidden rounded-md border-card border-dashed border-outline-variant bg-surface-low p-2 text-center transition-colors duration-fast hover:border-primary"
                >
                  {previews[s.id] ? (
                    <img src={previews[s.id]} alt="" className="h-full w-full rounded object-cover" />
                  ) : (
                    <span className="text-label text-ink-muted">{t(s.key)}</span>
                  )}
                  <input
                    ref={(el) => { fileInputs.current[s.id] = el; }}
                    id={s.id} type="file" accept="image/*" className="sr-only"
                    onChange={onFileChange(s.id)}
                  />
                </label>
              ))}
            </div>
            <p className="text-label text-ink-muted">{t('market.photos_hint')}</p>
          </fieldset>

          <div className="flex flex-wrap gap-3">
            <Button type="submit" loading={create.isPending}>
              {t(create.isPending ? 'common.loading' : 'market.submit_listing')}
            </Button>
            <Button type="button" variant="outline" onClick={() => navigate(-1)}>
              {t('common.cancel')}
            </Button>
          </div>
        </form>
      </Card>
    </div>
  );
}
