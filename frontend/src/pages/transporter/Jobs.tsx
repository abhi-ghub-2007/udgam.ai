import { Link } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { useTransporterDashboard } from '@/hooks/queries';
import {
  Badge, Card, CardSkeleton, EmptyState, ErrorState, PageHeader,
} from '@/components/ui';
import { money, date } from '@/utils/format';

/** Available jobs come from the transporter dashboard payload, which already
    lists orders awaiting transport -- no separate endpoint exists, and adding
    one would change the API contract for no functional gain. */
export default function Jobs() {
  const { t } = useTranslation();
  const q = useTransporterDashboard();
  const jobs = q.data?.available_jobs ?? [];

  return (
    <div className="space-y-6">
      <PageHeader title={t('transporter.available_jobs')} />
      {q.isLoading ? (
        <div className="space-y-4">{Array.from({ length: 3 }).map((_, i) => <CardSkeleton key={i} lines={2} />)}</div>
      ) : q.isError ? (
        <ErrorState
          title={t('common.error_title')} body={t('common.error_body')}
          retryLabel={t('common.retry')} onRetry={() => void q.refetch()}
        />
      ) : jobs.length === 0 ? (
        <EmptyState title={t('market.transport_none_title')} body={t('transporter.available_after_accept')} />
      ) : (
        <div className="space-y-4">
          {jobs.map((j) => (
            <Link key={j.id} to={`/transporter/jobs/${j.id}`} className="block">
              <Card className="space-y-3 transition-shadow duration-base hover:shadow-ambient animate-fade-up">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <h2 className="text-h2 font-semibold text-ink">{j.order_no}</h2>
                  <Badge tone="info">{t(`order.status.${j.status}`)}</Badge>
                </div>
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <span className="text-label text-ink-muted">
                    {t('transporter.cargo_value')}
                  </span>
                  <span className="tnum text-h2 font-bold text-primary">{money(j.subtotal_paise)}</span>
                </div>
                {j.needed_by && (
                  <p className="text-label text-ink-muted">
                    {t('market.needed_by')}: {date(j.needed_by)}
                  </p>
                )}
              </Card>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}
