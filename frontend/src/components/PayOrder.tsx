/**
 * B-3: buyer pays, order moves ACCEPTED -> PAYMENT_HELD.
 *
 * This step existed on the backend (POST /orders/{id}/pay, mock provider,
 * escrow_status 'held') with no way to trigger it from the UI at all -- every
 * order dead-ended at ACCEPTED, and a transporter accepting later got a real
 * but confusing "buyer hasn't paid" error with nothing pointing back here.
 *
 * There is no real payment rail yet (services/payments is mock-only), so this
 * is labelled as one rather than pretending money moved.
 */
import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { usePayOrder } from '@/hooks/queries';
import { ApiError } from '@/services/api/client';
import { Badge, Button } from '@/components/ui';
import { money } from '@/utils/format';
import type { Order } from '@/types/api';

export function PayOrder({ order, onDone }: { order: Order; onDone?: () => void }) {
  const { t } = useTranslation();
  const pay = usePayOrder(order.id);
  const [error, setError] = useState<string | null>(null);
  const [paid, setPaid] = useState(false);

  if (order.status !== 'ACCEPTED' && !paid) return null;

  const onPay = async () => {
    setError(null);
    try {
      await pay.mutateAsync();
      setPaid(true);
      onDone?.();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : t('common.error_body'));
    }
  };

  if (paid) return <Badge tone="success">{t('order.payment_held')}</Badge>;

  return (
    <div className="space-y-3 border-t border-line-card pt-4">
      {error && (
        <p role="alert" className="rounded-md bg-danger-container px-3 py-2 text-body text-danger-on-container">
          {error}
        </p>
      )}
      <div className="flex items-baseline justify-between gap-2">
        <span className="text-body text-ink-muted">{t('order.amount_to_pay')}</span>
        <span className="tnum text-h2 font-bold text-primary">{money(order.buyer_total_paise)}</span>
      </div>
      <Button loading={pay.isPending} onClick={() => void onPay()}>
        {t('order.pay_now')}
      </Button>
      <p className="text-label text-ink-muted">{t('order.pay_is_mock')}</p>
    </div>
  );
}
