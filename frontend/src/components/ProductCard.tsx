import { Link } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { Badge, cx } from '@/components/ui';
import { money, number } from '@/utils/format';
import type { Product } from '@/types/api';

const GRADE_TONE = { A: 'success', B: 'info', C: 'warning' } as const;

/** One produce listing. Used by farmer listings, buyer marketplace and both
    dashboards, so the same lot always looks the same wherever it appears. */
export function ProductCard({ product: p, to }: { product: Product; to: string }) {
  const { t } = useTranslation();
  return (
    <Link
      to={to}
      className={cx(
        'group flex flex-col gap-2 rounded-lg border-card border-line-card bg-surface p-4',
        'transition-shadow duration-base ease-udgam hover:shadow-ambient',
        'focus-visible:shadow-ambient',
      )}
    >
      <div className="flex items-start justify-between gap-2">
        <h3 className="min-w-0 truncate text-h2 font-semibold text-ink">
          {p.crop_name ?? t('market.produce')}
        </h3>
        {p.grade && (
          <Badge tone={GRADE_TONE[p.grade]}>{t('product.grade')} {p.grade}</Badge>
        )}
      </div>

      <p className="tnum text-stat font-bold text-primary">
        {money(p.asking_price_paise)}
        <span className="ml-1 text-body font-normal text-ink-muted">{t('common.per_kg')}</span>
      </p>

      <dl className="flex flex-wrap gap-x-4 gap-y-1 text-label text-ink-muted">
        <div className="flex gap-1">
          <dt className="sr-only">{t('market.available')}</dt>
          <dd>{number(p.available_quantity_kg)} {t('common.kg')}</dd>
        </div>
        {p.district && (
          <div className="flex gap-1">
            <dt className="sr-only">{t('auth.district')}</dt>
            <dd>{p.district}</dd>
          </div>
        )}
      </dl>
    </Link>
  );
}
