/**
 * F-4: the farmer's answer to an incoming order.
 *
 * Accepting reserves produce for a buyer and declining releases it, so both
 * are real commitments and neither is a quiet icon. Decline asks for a reason
 * before it fires — partly so the buyer learns something, partly so the
 * destructive option takes one more deliberate step than the safe one.
 *
 * The buttons only reflect what the state machine already permits; the server
 * re-checks the role and the transition, so nothing here is load-bearing for
 * authorisation.
 */
import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useOrderTransition } from '@/hooks/queries';
import { ApiError } from '@/services/api/client';
import { Badge, Button, Input } from '@/components/ui';
import type { Order } from '@/types/api';

export function OrderActions({ order, onDone }: { order: Order; onDone?: () => void }) {
  const { t } = useTranslation();
  const move = useOrderTransition(order.id);
  const [declining, setDeclining] = useState(false);
  const [reason, setReason] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState<'accepted' | 'declined' | null>(null);

  // Only a PLACED order is waiting on the farmer. Everything later is either
  // the buyer's move or the transporter's.
  if (order.status !== 'PLACED' && !done) return null;

  const send = async (to: 'ACCEPTED' | 'CANCELLED') => {
    setError(null);
    try {
      await move.mutateAsync({ to, note: to === 'CANCELLED' ? (reason || undefined) : undefined });
      setDone(to === 'ACCEPTED' ? 'accepted' : 'declined');
      onDone?.();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : t('common.error_body'));
    }
  };

  if (done) {
    return (
      <Badge tone={done === 'accepted' ? 'success' : 'neutral'}>
        {t(done === 'accepted' ? 'order.accepted_ok' : 'order.declined_ok')}
      </Badge>
    );
  }

  return (
    <div className="space-y-3 border-t border-line-card pt-4">
      {error && (
        <p role="alert" className="rounded-md bg-danger-container px-3 py-2 text-body text-danger-on-container">
          {error}
        </p>
      )}
      {declining ? (
        <>
          <label htmlFor={`why-${order.id}`} className="text-label text-ink-muted">
            {t('order.decline_reason')}
          </label>
          <Input id={`why-${order.id}`} value={reason} maxLength={500}
                 onChange={(e) => setReason(e.target.value)} />
          <div className="flex flex-wrap gap-3">
            <Button variant="danger" loading={move.isPending} onClick={() => void send('CANCELLED')}>
              {t('order.confirm_decline')}
            </Button>
            <Button variant="outline" onClick={() => setDeclining(false)}>{t('common.cancel')}</Button>
          </div>
        </>
      ) : (
        <>
          <div className="flex flex-wrap gap-3">
            <Button loading={move.isPending} onClick={() => void send('ACCEPTED')}>
              {t('order.accept')}
            </Button>
            <Button variant="outline" onClick={() => setDeclining(true)}>
              {t('order.decline')}
            </Button>
          </div>
          <p className="text-label text-ink-muted">{t('order.accept_hint')}</p>
        </>
      )}
    </div>
  );
}
