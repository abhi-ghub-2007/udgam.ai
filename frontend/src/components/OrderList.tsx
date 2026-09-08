import { useState } from 'react';
import { Link } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { Badge, Card, CardSkeleton, EmptyState, ErrorState, cx } from '@/components/ui';
import { money, number, date } from '@/utils/format';
import type { Order, OrderStatus } from '@/types/api';

/** Status groups a user thinks in, mapped onto the order state machine. */
const FILTERS: Record<string, OrderStatus[] | null> = {
  all: null,
  active: ['PLACED', 'ACCEPTED', 'PAYMENT_HELD', 'LOGISTICS_ASSIGNED', 'PICKED_UP', 'IN_TRANSIT'],
  delivered: ['DELIVERED', 'CLOSED'],
  cancelled: ['CANCELLED', 'DISPUTED'],
};

const TONE: Partial<Record<OrderStatus, 'success' | 'info' | 'danger' | 'warning'>> = {
  CLOSED: 'success', DELIVERED: 'success',
  CANCELLED: 'danger', DISPUTED: 'danger',
  IN_TRANSIT: 'info', PICKED_UP: 'info', LOGISTICS_ASSIGNED: 'info',
};

interface Props {
  orders: Order[] | undefined;
  loading: boolean; error: boolean; onRetry: () => void;
  /** Which side of the trade the viewer is on -- changes the money shown. */
  side: 'farmer' | 'buyer';
  linkTo?: (o: Order) => string;
}

export function OrderList({ orders, loading, error, onRetry, side, linkTo }: Props) {
  const { t } = useTranslation();
  const [active, setActive] = useState('all');
  const all = orders ?? [];
  const allowed = FILTERS[active];
  const rows = allowed ? all.filter((o) => allowed.includes(o.status)) : all;

  if (loading) {
    return <div className="space-y-4">{Array.from({ length: 3 }).map((_, i) => <CardSkeleton key={i} lines={2} />)}</div>;
  }
  if (error) {
    return <ErrorState title={t('common.error_title')} body={t('common.error_body')}
                       retryLabel={t('common.retry')} onRetry={onRetry} />;
  }

  return (
    <div className="space-y-4">
      <div role="tablist" aria-label={t('market.orders_title')} className="flex flex-wrap gap-2">
        {Object.keys(FILTERS).map((k) => {
          const count = FILTERS[k] ? all.filter((o) => FILTERS[k]!.includes(o.status)).length : all.length;
          const on = k === active;
          return (
            <button key={k} role="tab" aria-selected={on} onClick={() => setActive(k)}
              className={cx('min-h-tap rounded-full px-4 text-body font-medium transition-colors duration-fast',
                on ? 'bg-primary text-primary-on' : 'bg-surface-high text-ink-muted hover:bg-surface-highest')}>
              {t(`market.orders_filter.${k}`)} ({count})
            </button>
          );
        })}
      </div>

      {rows.length === 0 ? (
        <EmptyState title={all.length ? t('market.orders_none_in_filter') : t('market.orders_empty')} />
      ) : (
        <div className="space-y-4">
          {rows.map((o) => {
            const item = o.items?.[0];
            const extra = (o.items?.length ?? 0) - 1;
            const body = (
              <Card className="space-y-3 transition-shadow duration-base hover:shadow-ambient">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <h3 className="text-h2 font-semibold text-ink">{o.order_no}</h3>
                  <Badge tone={TONE[o.status] ?? 'warning'}>{t(`order.status.${o.status}`)}</Badge>
                </div>
                <p className="text-body text-ink-muted">
                  {item?.crop_name ?? t('market.produce')} · {number(item?.quantity_kg ?? 0)} {t('common.kg')}
                  {extra > 0 && ` · ${t('market.plus_more_items', { n: extra })}`}
                </p>
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <span className="text-label text-ink-muted">
                    {t(side === 'farmer' ? 'market.buyer_label' : 'market.farmer_label')}:{' '}
                    {o.counterparty?.full_name ?? '—'}
                  </span>
                  <span className="text-label text-ink-muted">{date(o.placed_at ?? o.created_at)}</span>
                </div>
                <div className="flex items-baseline justify-between gap-2 border-t border-line-card pt-3">
                  <span className="text-body text-ink-muted">
                    {t(side === 'farmer' ? 'market.your_payout' : 'market.total_value')}
                  </span>
                  <span className="tnum text-h2 font-bold text-primary">
                    {money(side === 'farmer' ? o.farmer_payout_paise : o.buyer_total_paise)}
                  </span>
                </div>
              </Card>
            );
            return linkTo
              ? <Link key={o.id} to={linkTo(o)} className="block">{body}</Link>
              : <div key={o.id}>{body}</div>;
          })}
        </div>
      )}
    </div>
  );
}
