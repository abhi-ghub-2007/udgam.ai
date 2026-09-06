import { useTranslation } from 'react-i18next';
import { cx } from '@/components/ui';
import type { ShipmentStatus } from '@/types/api';

/** The journey, in the order it happens: farm -> pickup -> transit -> buyer. */
const JOURNEY: ShipmentStatus[] = ['created', 'assigned', 'picked_up', 'in_transit', 'delivered'];

/**
 * Logistics as a progress trail rather than a status word. The connector line
 * animates with a transform (never a layout property), and is purely decorative
 * -- the state is also conveyed by colour AND the step label, so it survives
 * reduced-motion and screen readers.
 */
export function ShipmentTimeline({ status }: { status: ShipmentStatus }) {
  const { t } = useTranslation();
  if (status === 'cancelled') {
    return <p className="text-body font-medium text-danger">{t('market.shipment_step.cancelled')}</p>;
  }
  const at = JOURNEY.indexOf(status);

  return (
    <ol className="flex items-center gap-1" aria-label={t('market.transport_title')}>
      {JOURNEY.map((step, i) => {
        const done = i <= at;
        return (
          <li key={step} className="flex min-w-0 flex-1 items-center gap-1">
            <div className="flex min-w-0 flex-col items-center gap-1">
              <span
                aria-hidden
                className={cx('h-2.5 w-2.5 shrink-0 rounded-full',
                  done ? 'bg-primary' : 'bg-surface-highest')}
              />
              <span className={cx('truncate text-[11px] leading-tight text-center',
                done ? 'font-semibold text-ink' : 'text-ink-muted')}>
                {t(`market.shipment_step.${step}`)}
              </span>
            </div>
            {i < JOURNEY.length - 1 && (
              <span aria-hidden
                className={cx('h-0.5 flex-1 origin-left rounded-full',
                  i < at ? 'bg-primary animate-draw-line' : 'bg-surface-highest')} />
            )}
          </li>
        );
      })}
    </ol>
  );
}
