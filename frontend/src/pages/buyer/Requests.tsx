import { useTranslation } from 'react-i18next';
import { useMyRequests } from '@/hooks/queries';
import { Badge, Card, CardSkeleton, EmptyState, ErrorState, LinkButton, PageHeader } from '@/components/ui';
import { money, number, date } from '@/utils/format';

export default function Requests() {
  const { t } = useTranslation();
  const q = useMyRequests();

  return (
    <div className="space-y-6">
      <PageHeader
        title={t('nav.my_requests')}
        actions={<LinkButton to="/buyer/requests/new">{t('buyer.post_requirement')}</LinkButton>}
      />
      {q.isLoading ? (
        <div className="grid gap-4 sm:grid-cols-2">
          {Array.from({ length: 4 }).map((_, i) => <CardSkeleton key={i} lines={2} />)}
        </div>
      ) : q.isError ? (
        <ErrorState
          title={t('common.error_title')} body={t('common.error_body')}
          retryLabel={t('common.retry')} onRetry={() => void q.refetch()}
        />
      ) : (q.data ?? []).length === 0 ? (
        <EmptyState
          title={t('market.no_requests')}
          action={<LinkButton to="/buyer/requests/new">{t('buyer.post_requirement')}</LinkButton>}
        />
      ) : (
        <div className="grid gap-4 sm:grid-cols-2">
          {q.data!.map((r) => (
            <Card key={r.id} className="space-y-2 animate-fade-up">
              <div className="flex items-start justify-between gap-2">
                <h2 className="text-h2 font-semibold text-ink">{r.crop_name}</h2>
                <Badge tone={r.status === 'open' ? 'success' : 'neutral'}>
                  {t(`market.request_status.${r.status}`)}
                </Badge>
              </div>
              <p className="tnum text-body text-ink-muted">
                {number(r.quantity_kg)} {t('common.kg')}
              </p>
              <p className="tnum text-body text-ink-muted">
                {r.target_price_paise != null
                  ? `${t('market.target_price')}: ${money(r.target_price_paise)} ${t('common.per_kg')}`
                  : t('market.no_target_price')}
              </p>
              {r.needed_by && (
                <p className="text-label text-ink-muted">
                  {t('market.needed_by')}: {date(r.needed_by)}
                </p>
              )}
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
