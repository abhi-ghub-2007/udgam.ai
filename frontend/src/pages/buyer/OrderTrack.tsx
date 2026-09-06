import { useNavigate, useParams } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { useOrder } from '@/hooks/queries';
import { useAuth } from '@/services/auth/AuthProvider';
import { OrderActions } from '@/components/OrderActions';
import { TransportPanel } from '@/components/TransportPanel';
import { ReputationPanel, ReviewPanel } from '@/components/Reputation';
import { Badge, Button, Card, CardSkeleton, CardTitle, ErrorState, PageHeader, cx } from '@/components/ui';
import { money, number, date } from '@/utils/format';
import type { OrderStatus } from '@/types/api';

/** The order's journey, in the order it happens. Cancelled/disputed are
    terminal branches, not steps, so they are shown separately. */
const JOURNEY: OrderStatus[] = [
  'PLACED', 'ACCEPTED', 'PAYMENT_HELD', 'LOGISTICS_ASSIGNED',
  'PICKED_UP', 'IN_TRANSIT', 'DELIVERED', 'CLOSED',
];

/**
 * One order, seen by whichever side is looking at it.
 *
 * Both the buyer and the farmer route here. The page decides what to offer
 * from the viewer's role and the order's state, rather than being duplicated
 * per side: a farmer sees accept/decline while the order is still PLACED, the
 * party named by logistics_arranged_by gets the transport controls and the
 * other party sees the same arrangements read-only, and reviewing appears once
 * the order is finished.
 */
export default function OrderTrack() {
  const { id } = useParams();
  const { t } = useTranslation();
  const navigate = useNavigate();
  const { profile } = useAuth();
  const q = useOrder(id);

  if (q.isLoading) return <CardSkeleton lines={6} />;
  if (q.isError || !q.data) {
    return (
      <ErrorState
        title={t('common.error_title')} body={t('common.error_body')}
        retryLabel={t('common.retry')} onRetry={() => void q.refetch()}
      />
    );
  }
  const o = q.data;
  const terminal = o.status === 'CANCELLED' || o.status === 'DISPUTED';
  const at = JOURNEY.indexOf(o.status);
  const myRole = profile?.role;
  const isFarmer = myRole === 'farmer';
  // The transport controls belong to exactly one side, named on the order.
  const canArrange = Boolean(o.logistics_arranged_by && myRole === o.logistics_arranged_by);
  // Whose reputation is worth showing here is the other side of this trade.
  const counterpartyId = isFarmer ? o.buyer_id : o.farmer_id;

  return (
    <div className="space-y-6">
      <PageHeader title={o.order_no} subtitle={t('order.track_title')} />

      <Card className="max-w-2xl space-y-5">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <CardTitle>{t('order.track_title')}</CardTitle>
          <Badge tone={terminal ? 'danger' : o.status === 'CLOSED' ? 'success' : 'info'}>
            {t(`order.status.${o.status}`)}
          </Badge>
        </div>

        {terminal ? (
          <p className="text-body font-medium text-danger">{t(`order.status.${o.status}`)}</p>
        ) : (
          <ol className="space-y-0">
            {JOURNEY.map((s, i) => {
              const done = i <= at;
              return (
                <li key={s} className="flex gap-3">
                  <div className="flex flex-col items-center">
                    <span aria-hidden className={cx('mt-1.5 h-3 w-3 shrink-0 rounded-full',
                      done ? 'bg-primary' : 'bg-surface-highest')} />
                    {i < JOURNEY.length - 1 && (
                      <span aria-hidden className={cx('w-0.5 flex-1',
                        i < at ? 'bg-primary' : 'bg-surface-highest')} />
                    )}
                  </div>
                  <span className={cx('pb-5 text-body',
                    done ? 'font-semibold text-ink' : 'text-ink-muted')}>
                    {t(`order.status.${s}`)}
                  </span>
                </li>
              );
            })}
          </ol>
        )}

        <dl className="grid gap-3 border-t border-line-card pt-4 sm:grid-cols-2">
          <div>
            {/* GET /api/orders/{id} returns both profiles directly -- unlike
                the list endpoint it has no viewer-aware "counterparty", so the
                page picks whichever side the viewer is NOT. */}
            <dt className="text-label text-ink-muted">
              {t(isFarmer ? 'market.buyer_label' : 'market.farmer_label')}
            </dt>
            <dd className="text-body font-semibold">
              {(isFarmer ? o.buyer?.full_name : o.farmer?.full_name) ?? '—'}
            </dd>
          </div>
          {o.placed_at && (
            <div>
              <dt className="text-label text-ink-muted">{t('order.track_title')}</dt>
              <dd className="text-body font-semibold">{date(o.placed_at)}</dd>
            </div>
          )}
        </dl>

        {o.items?.length > 0 && (
          <ul className="space-y-1 border-t border-line-card pt-4">
            {o.items.map((it, i) => (
              <li key={i} className="flex justify-between gap-3 text-body">
                <span>{it.crop_name ?? t('market.produce')} · {number(it.quantity_kg)} {t('common.kg')}</span>
                <span className="tnum">{money(it.unit_price_paise)} {t('common.per_kg')}</span>
              </li>
            ))}
          </ul>
        )}

        <div className="flex items-baseline justify-between border-t border-line-card pt-4">
          <span className="text-body text-ink-muted">
            {t(isFarmer ? 'market.your_payout' : 'market.total_value')}
          </span>
          <span className="tnum text-h1 font-bold text-primary">
            {money(isFarmer ? o.farmer_payout_paise : o.buyer_total_paise)}
          </span>
        </div>

        {/* The farmer's answer, while the order is still waiting on it. */}
        {isFarmer && <OrderActions order={o} onDone={() => void q.refetch()} />}
        {!isFarmer && o.status === 'PLACED' && (
          <p className="text-label text-ink-muted">{t('order.awaiting_farmer')}</p>
        )}

        <Button variant="outline" onClick={() => navigate(-1)}>{t('common.back')}</Button>
      </Card>

      {/* Transport only becomes a question once the farmer has agreed to sell. */}
      {!terminal && o.status !== 'PLACED' && (
        <div className="max-w-2xl">
          <TransportPanel order={o} shipment={o.shipment ?? null} canArrange={canArrange} />
        </div>
      )}

      <div className="max-w-2xl space-y-6">
        <ReviewPanel orderId={o.id} />
        {counterpartyId && (
          <ReputationPanel
            profileId={counterpartyId}
            role={isFarmer ? 'buyer' : 'farmer'}
          />
        )}
      </div>
    </div>
  );
}
