/**
 * B-2: product detail + checkout (PRD §8 step 1).
 *
 * The React migration dropped the entire purchase form from this page --
 * there was a listing to look at, but no way to buy it. This restores the
 * legacy flow: pick a quantity, choose who arranges transport, submit one
 * authoritative POST /api/orders. The backend re-validates quantity against
 * what is actually still available and computes the price itself from the
 * listing's asking_price_paise (services/pricing.py) -- nothing the buyer
 * enters here can change what they are charged; the subtotal shown before
 * submitting is a preview, not the source of truth.
 */
import { useRef, useState, type FormEvent } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { useCreateOrder, useProduct } from '@/hooks/queries';
import { ApiError } from '@/services/api/client';
import {
  Badge, Button, Card, CardSkeleton, ErrorState, Field, Input, PageHeader, Select,
} from '@/components/ui';
import { ReputationPanel } from '@/components/Reputation';
import { money, number, date } from '@/utils/format';
import type { Order } from '@/types/api';

export default function BuyerProduct() {
  const { id } = useParams();
  const { t } = useTranslation();
  const navigate = useNavigate();
  const q = useProduct(id);
  const createOrder = useCreateOrder();

  const [quantity, setQuantity] = useState('');
  const [logistics, setLogistics] = useState<'buyer' | 'farmer'>('farmer');
  const [error, setError] = useState<string | null>(null);
  const [placed, setPlaced] = useState<Order | null>(null);
  // A ref, not just createOrder.isPending: React state updates (and the
  // Button's disabled attribute with them) land on the NEXT render, but a
  // fast double-click dispatches two submit events in the same tick, before
  // that render happens -- disabling on isPending alone let one real click
  // place two, three, or more identical orders. This flag is set the instant
  // the first submit starts, synchronously, so the second submit event bails
  // before it ever calls the mutation.
  const submitting = useRef(false);

  if (q.isLoading) return <CardSkeleton lines={5} />;
  if (q.isError || !q.data) {
    return (
      <ErrorState title={t('common.error_title')} body={t('common.error_body')}
                  retryLabel={t('common.retry')} onRetry={() => void q.refetch()} />
    );
  }
  const p = q.data;
  const isAvailable = p.status === 'active' && p.available_quantity_kg > 0;
  const qtyNumber = Number(quantity);
  // Preview only -- the actual amount is computed server-side from the
  // listing's own price, never from anything this form sends.
  const previewSubtotal = qtyNumber > 0 ? Math.round(qtyNumber * p.asking_price_paise) : 0;

  if (placed) {
    return (
      <div className="space-y-6">
        <PageHeader title={t('market.order_placed_title')} />
        <Card className="max-w-2xl space-y-4 border-insight/25 bg-insight/5 animate-fade-up">
          <p className="text-body text-ink">
            {t('market.order_placed_body', {
              farmer: placed.farmer?.full_name ?? t('market.farmer_label'),
              quantity: number(qtyNumber),
              crop: p.crop_name ?? t('market.produce'),
            })}
          </p>
          <dl className="grid gap-3 border-t border-line-card pt-4 sm:grid-cols-2">
            <div>
              <dt className="text-label text-ink-muted">{t('order.track_title')}</dt>
              <dd className="text-body font-semibold">{placed.order_no}</dd>
            </div>
            <div>
              <dt className="text-label text-ink-muted">{t('market.total_value')}</dt>
              <dd className="tnum text-body font-semibold">{money(placed.buyer_total_paise)}</dd>
            </div>
          </dl>
          <Button block onClick={() => navigate(`/buyer/orders/${placed.id}`, { replace: true })}>
            {t('market.view_order')}
          </Button>
        </Card>
      </div>
    );
  }

  const onSubmit = async (e: FormEvent) => {
    e.preventDefault();
    if (submitting.current) return;
    setError(null);
    if (!(qtyNumber > 0)) {
      setError(t('market.err_order_quantity'));
      return;
    }
    if (qtyNumber > p.available_quantity_kg) {
      setError(t('market.err_quantity'));
      return;
    }
    submitting.current = true;
    try {
      const order = await createOrder.mutateAsync({
        product_id: p.id,
        farmer_id: p.farmer_id,
        quantity_kg: qtyNumber,
        logistics_arranged_by: logistics,
      });
      setPlaced(order);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : t('common.error_body'));
      submitting.current = false;
    }
  };

  return (
    <div className="space-y-6">
      <PageHeader title={p.crop_name ?? t('market.detail_title')} />
      <Card className="max-w-2xl space-y-4">
        <div className="flex flex-wrap items-center gap-2">
          {p.grade && <Badge tone="info">{t('product.grade')} {p.grade}</Badge>}
          {p.grade_method && <Badge tone="insight">{t(`ai.method_${p.grade_method}`)}</Badge>}
          {p.district && <Badge>{p.district}</Badge>}
        </div>

        <p className="tnum text-display font-bold text-primary">
          {money(p.asking_price_paise)}
          <span className="ml-1 text-body font-normal text-ink-muted">{t('common.per_kg')}</span>
        </p>

        <dl className="grid gap-3 sm:grid-cols-2">
          <div>
            <dt className="text-label text-ink-muted">{t('market.available')}</dt>
            <dd className="tnum text-body font-semibold">
              {number(p.available_quantity_kg)} {t('common.kg')}
            </dd>
          </div>
          {p.harvest_date && (
            <div>
              <dt className="text-label text-ink-muted">{t('market.harvest_date')}</dt>
              <dd className="text-body font-semibold">{date(p.harvest_date)}</dd>
            </div>
          )}
          {p.farmer_name && (
            <div>
              <dt className="text-label text-ink-muted">{t('market.farmer_label')}</dt>
              <dd className="text-body font-semibold">{p.farmer_name}</dd>
            </div>
          )}
        </dl>

        {p.description && <p className="text-body text-ink-muted">{p.description}</p>}
      </Card>

      {isAvailable ? (
        <Card className="max-w-2xl space-y-4 border-primary/25">
          <h2 className="text-h2 font-bold text-ink">{t('buyer.purchase_request')}</h2>
          <form onSubmit={onSubmit} noValidate className="space-y-4">
            {error && (
              <p role="alert" className="rounded-md bg-danger-container px-3 py-2 text-body text-danger-on-container">
                {error}
              </p>
            )}

            <Field label={t('market.quantity_kg')} htmlFor="qty" required>
              <Input id="qty" type="number" inputMode="decimal" min="1" step="0.01"
                     max={p.available_quantity_kg} value={quantity}
                     onChange={(e) => { setQuantity(e.target.value); setError(null); }} />
            </Field>

            <Field label={t('market.logistics_label')} htmlFor="logistics"
                   hint={logistics === 'buyer' ? t('market.logistics_hint_buyer') : t('market.logistics_hint_farmer')}>
              <Select id="logistics" value={logistics}
                      onChange={(e) => setLogistics(e.target.value as 'buyer' | 'farmer')}>
                <option value="farmer">{t('market.logistics_farmer')}</option>
                <option value="buyer">{t('market.logistics_buyer')}</option>
              </Select>
            </Field>

            {qtyNumber > 0 && (
              <div className="flex items-baseline justify-between border-t border-line-card pt-4">
                <span className="text-body text-ink-muted">{t('market.subtotal')}</span>
                <span className="tnum text-h2 font-bold text-primary">{money(previewSubtotal)}</span>
              </div>
            )}

            <Button type="submit" block loading={createOrder.isPending}>
              {t(createOrder.isPending ? 'market.placing_order' : 'market.place_order')}
            </Button>
          </form>
        </Card>
      ) : (
        <Card className="max-w-2xl">
          <p className="text-body text-ink-muted">{t('market.no_longer_available')}</p>
        </Card>
      )}

      {/* The farmer's record, next to the decision to buy from them — the
          point at which it is worth anything (§20). */}
      <div className="max-w-2xl">
        <ReputationPanel profileId={p.farmer_id} role="farmer" />
      </div>

      <Button variant="outline" onClick={() => navigate(-1)}>{t('common.back')}</Button>
    </div>
  );
}
