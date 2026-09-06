import { useTranslation } from 'react-i18next';
import { useTransportEarnings, useTransporterDashboard } from '@/hooks/queries';
import { CardSkeleton, ErrorState, PageHeader, StatCard, StatSkeleton } from '@/components/ui';
import { money, number } from '@/utils/format';

export default function Earnings() {
  const { t } = useTranslation();
  const q = useTransportEarnings();
  const dash = useTransporterDashboard();

  if (q.isError) {
    return (
      <div className="space-y-6">
        <PageHeader title={t('transporter.earnings_summary')} />
        <ErrorState
          title={t('common.error_title')} body={t('common.error_body')}
          retryLabel={t('common.retry')} onRetry={() => void q.refetch()}
        />
      </div>
    );
  }

  const e = q.data ?? {};
  const loading = q.isLoading || dash.isLoading;

  return (
    <div className="space-y-6">
      <PageHeader title={t('transporter.earnings_summary')} />

      <section className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {loading ? Array.from({ length: 4 }).map((_, i) => <StatSkeleton key={i} />) : <>
          <StatCard
            label={t('transporter.earnings_summary')}
            value={money(dash.data?.total_earnings_paise ?? e.total_paise ?? 0, { compact: true })}
            tone="primary"
          />
          <StatCard
            label={t('farmer.dashboard.earnings_expected')}
            value={money(dash.data?.earnings_month_paise ?? 0, { compact: true })}
            tone="secondary"
          />
          <StatCard
            label={t('transporter.history')}
            value={String(dash.data?.completed_deliveries ?? 0)}
          />
          <StatCard
            label={t('market.distance_label')}
            value={`${number(Math.round(e.total_distance_km ?? 0))} km`}
          />
        </>}
      </section>

      {loading && <CardSkeleton lines={3} />}
    </div>
  );
}
