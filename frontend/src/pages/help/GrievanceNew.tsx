/**
 * Report an issue.
 *
 * PROGRESSIVE DISCLOSURE IS THE POINT
 * -----------------------------------
 * There are eighteen things that can go wrong on this platform. Showing a
 * farmer eighteen radio buttons while their produce is sitting in a truck is
 * how you get "Other" selected every time and a support queue full of unusable
 * cases. So: six groups first, then the handful that belong to the one chosen.
 *
 * CONTEXT IS TAKEN, NOT ASKED FOR
 * -------------------------------
 * When this page is reached from an order (`?order=<id>`), that id is all the
 * client sends. The respondent, the shipment, and the order's status at this
 * moment are read SERVER-SIDE from the order -- a client that could name its
 * own respondent could file a complaint against a stranger.
 *
 * The vocabulary itself comes from GET /taxonomy rather than being hardcoded
 * here, so a category this screen offers is always one the server accepts.
 */
import { useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { useCreateGrievance, useGrievanceTaxonomy, useOrder } from '@/hooks/queries';
import { ApiError } from '@/services/api/client';
import {
  Button, Card, CardSkeleton, CardTitle, Field, PageHeader, Textarea, cx,
} from '@/components/ui';

export default function GrievanceNew() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const orderId = params.get('order') ?? undefined;

  const { data: taxonomy, isLoading } = useGrievanceTaxonomy();
  // Only to SHOW the user what they are attaching. The backend re-reads the
  // order itself; nothing displayed here is trusted on submit.
  const { data: order } = useOrder(orderId);
  const create = useCreateGrievance();

  const [category, setCategory] = useState<string | null>(null);
  const [subcategory, setSubcategory] = useState<string | null>(null);
  const [description, setDescription] = useState('');
  const [error, setError] = useState<string | null>(null);

  if (isLoading || !taxonomy) return <CardSkeleton lines={5} />;

  const categories = Object.keys(taxonomy.categories);
  const subs = category ? taxonomy.categories[category] ?? [] : [];
  // Account and verification problems are ours; there is no counterparty to
  // answer them, so we say so rather than letting the user expect a reply.
  const platformOnly = category ? taxonomy.platform_only.includes(category) : false;

  const onSubmit = async () => {
    if (!category || !subcategory) return;
    setError(null);
    try {
      const res = await create.mutateAsync({
        category, subcategory,
        description: description.trim(),
        // Context follows the category: a complaint about our verification
        // queue has no business carrying somebody's order with it.
        related_order_id: platformOnly ? null : orderId ?? null,
      });
      navigate(`/help/${res.case.id}`, { replace: true });
    } catch (err) {
      setError(err instanceof ApiError ? err.message : t('common.error_body'));
    }
  };

  const choice = (active: boolean) => cx(
    'w-full rounded-lg border-card px-4 py-3 text-left text-body font-medium',
    'min-h-tap transition-colors duration-fast ease-udgam',
    active
      ? 'border-primary bg-primary-container text-primary-on-container'
      : 'border-outline-variant bg-surface text-ink hover:bg-surface-low',
  );

  return (
    <div className="max-w-2xl space-y-6">
      <PageHeader title={t('grievance.new_title')} subtitle={t('grievance.new_subtitle')} />

      {/* What the case will be attached to. Shown BEFORE the questions so the
          user can see we already know it and does not start typing it in. */}
      {orderId && order && !platformOnly && (
        <Card className="space-y-1">
          <CardTitle>{t('grievance.attached_title')}</CardTitle>
          <p className="text-body text-ink">{order.order_no}</p>
          <p className="text-label text-ink-muted">
            {t('grievance.attached_status', {
              status: t(`order.status.${order.status}`, {
                defaultValue: order.status,
              }),
            })}
          </p>
        </Card>
      )}

      {/* ------------------------------------------------ step 1: the group */}
      <Card className="space-y-3">
        <CardTitle>{t('grievance.q_what')}</CardTitle>
        <div className="grid gap-2 sm:grid-cols-2">
          {categories.map((c) => (
            <button
              key={c} type="button"
              aria-pressed={category === c}
              className={choice(category === c)}
              onClick={() => { setCategory(c); setSubcategory(null); setError(null); }}
            >
              {t(`grievance.cat_${c}`)}
            </button>
          ))}
        </div>
      </Card>

      {/* --------------------------------------- step 2: the specific thing */}
      {category && (
        <Card className="space-y-3">
          <CardTitle>{t('grievance.q_which')}</CardTitle>
          <div className="grid gap-2">
            {subs.map((s) => (
              <button
                key={s} type="button"
                aria-pressed={subcategory === s}
                className={choice(subcategory === s)}
                onClick={() => { setSubcategory(s); setError(null); }}
              >
                {t(`grievance.sub_${s}`)}
              </button>
            ))}
          </div>
          {platformOnly && (
            <p className="text-label text-ink-muted">{t('grievance.platform_note')}</p>
          )}
        </Card>
      )}

      {/* ------------------------------------------ step 3: what happened */}
      {subcategory && (
        <Card className="space-y-4">
          <Field label={t('grievance.q_describe')} htmlFor="grv-desc"
                 hint={t('grievance.describe_hint')} required>
            <Textarea
              id="grv-desc" rows={5} value={description} maxLength={2000}
              onChange={(e) => { setDescription(e.target.value); setError(null); }}
            />
          </Field>

          {error && (
            <p role="alert"
               className="rounded-md bg-danger-container px-3 py-2 text-body text-danger-on-container">
              {error}
            </p>
          )}

          {/* Evidence is attached on the case itself, once it exists. Asking
              for a photo before there is anywhere to put it means an upload
              that can fail and take the whole report with it. */}
          <p className="text-label text-ink-muted">{t('grievance.evidence_later')}</p>

          <div className="flex flex-wrap gap-2">
            <Button
              loading={create.isPending}
              disabled={description.trim().length < 10}
              onClick={() => void onSubmit()}
            >
              {t('grievance.submit')}
            </Button>
            <Button variant="outline" onClick={() => navigate('/help')}>
              {t('common.cancel')}
            </Button>
          </div>
        </Card>
      )}
    </div>
  );
}
