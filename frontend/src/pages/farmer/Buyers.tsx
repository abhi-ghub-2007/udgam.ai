import { useTranslation } from 'react-i18next';
import { useMatchingBuyers } from '@/hooks/queries';
import { Badge, Card, CardSkeleton, EmptyState, ErrorState, PageHeader } from '@/components/ui';
import { money, number, date } from '@/utils/format';

export default function Buyers() {
  const { t } = useTranslation();
  const q = useMatchingBuyers();

  return (
    <div className="space-y-6">
      <PageHeader title={t('market.matching_title')} subtitle={t('market.for_your_crops')} />
      {q.isLoading ? (
        <div className="space-y-4">{Array.from({ length: 3 }).map((_, i) => <CardSkeleton key={i} lines={2} />)}</div>
      ) : q.isError ? (
        <ErrorState title={t('common.error_title')} body={t('common.error_body')}
                    retryLabel={t('common.retry')} onRetry={() => void q.refetch()} />
      ) : (q.data ?? []).length === 0 ? (
        <EmptyState title={t('market.no_matches')} />
      ) : (
        <div className="space-y-4">
          {q.data!.map((m) => (
            <Card key={m.id} className="space-y-3 animate-fade-up">
              <div className="flex flex-wrap items-start justify-between gap-2">
                <h2 className="text-h2 font-semibold text-ink">
                  {m.crop_name} · {number(m.quantity_kg)} {t('common.kg')}
                </h2>
                <Badge tone="insight">{t('ai.method_ALGORITHMIC')}</Badge>
              </div>
              <div className="flex flex-wrap gap-x-5 gap-y-1 text-body text-ink-muted">
                {m.target_price_paise != null && (
                  <span className="tnum">
                    {t('market.target_price')}: <strong className="text-ink">{money(m.target_price_paise)}</strong> {t('common.per_kg')}
                  </span>
                )}
                {m.delivery_district && <span>{m.delivery_district}</span>}
                {m.needed_by && <span>{t('market.needed_by')}: {date(m.needed_by)}</span>}
              </div>
              {m.reasons?.length > 0 && (
                <ul className="space-y-1">
                  {m.reasons.map((r, i) => (
                    <li key={i} className="flex gap-2 text-body text-ink-muted">
                      <span aria-hidden className="mt-2 h-1.5 w-1.5 shrink-0 rounded-full bg-primary" />{r}
                    </li>
                  ))}
                </ul>
              )}
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
