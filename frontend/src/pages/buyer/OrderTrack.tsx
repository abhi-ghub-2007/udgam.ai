import { useNavigate, useParams } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { useOrder } from '@/hooks/queries';
import { Badge, Button, Card, CardSkeleton, CardTitle, ErrorState, PageHeader, cx } from '@/components/ui';
import { money, number, date } from '@/utils/format';
import type { OrderStatus } from '@/types/api';

/** The order's journey, in the order it happens. Cancelled/disputed are
    terminal branches, not steps, so they are shown separately. */
const JOURNEY: OrderStatus[] = [
  'PLACED', 'ACCEPTED', 'PAYMENT_HELD', 'LOGISTICS_ASSIGNED',
  'PICKED_UP', 'IN_TRANSIT', 'DELIVERED', 'CLOSED',
];

export default function OrderTrack() {
  const { id } = useParams();
  const { t } = useTranslation();
  const navigate = useNavigate();
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
            <dt className="text-label text-ink-muted">{t('market.farmer_label')}</dt>
            <dd className="text-body font-semibold">{o.counterparty?.full_name ?? '—'}</dd>
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
          <span className="text-body text-ink-muted">{t('market.total_value')}</span>
          <span className="tnum text-h1 font-bold text-primary">{money(o.buyer_total_paise)}</span>
        </div>

        <Button variant="outline" onClick={() => navigate(-1)}>{t('common.back')}</Button>
      </Card>
    </div>
  );
}
