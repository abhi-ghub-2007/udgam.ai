import { useTranslation } from 'react-i18next';
import { Link } from 'react-router-dom';
import { useTransporterDashboard } from '@/hooks/queries';
import { useAuth } from '@/services/auth/AuthProvider';
import {
  Badge, Card, CardSkeleton, CardTitle, EmptyState, ErrorState, LinkButton,
  PageHeader, StatCard, StatSkeleton,
} from '@/components/ui';
import { ShipmentTimeline } from '@/components/ShipmentTimeline';
import { money, number, date } from '@/utils/format';

export default function TransporterHome() {
  const { t } = useTranslation();
  const { profile } = useAuth();
  const q = useTransporterDashboard();
  const d = q.data;

  return (
    <div className="space-y-6">
      <PageHeader
        title={t('farmer.dashboard.greeting', { name: profile?.full_name ?? '' })}
        actions={<>
          <LinkButton to="/transporter/capacity/new">{t('transporter.route_plan')}</LinkButton>
          <LinkButton to="/transporter/jobs" variant="outline">{t('transporter.available_jobs')}</LinkButton>
        </>}
      />

      <section className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {q.isLoading ? Array.from({ length: 4 }).map((_, i) => <StatSkeleton key={i} />) : <>
          <StatCard label={t('transporter.available_jobs')} value={String(d?.active_jobs ?? 0)} tone="primary" />
          <StatCard label={t('transporter.earnings_summary')}
                    value={money(d?.earnings_month_paise, { compact: true })} tone="secondary" />
          <StatCard label={t('transporter.history')} value={String(d?.completed_deliveries ?? 0)} />
          <StatCard label={t('transporter.optimized_route')} value={String(d?.pending_consolidation ?? 0)} />
        </>}
      </section>

      <section className="space-y-3">
        <CardTitle>{t('transporter.job_details')}</CardTitle>
        {q.isLoading ? <CardSkeleton />
          : q.isError ? (
            <ErrorState title={t('common.error_title')} body={t('common.error_body')}
                        retryLabel={t('common.retry')} onRetry={() => void q.refetch()} />
          ) : (d?.upcoming_pickups ?? []).length === 0 ? (
            <EmptyState title={t('market.transport_none_title')}
                        action={<LinkButton to="/transporter/jobs">{t('transporter.available_jobs')}</LinkButton>} />
          ) : (
            <div className="space-y-4">
              {d!.upcoming_pickups.map((s) => (
                <Card key={s.id} className="space-y-4 animate-fade-up">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <Link to={`/transporter/deliveries/${s.id}`}
                          className="text-h2 font-semibold text-ink underline-offset-2 hover:underline">
                      {s.order_no ?? t('market.shipment')}
                    </Link>
                    <Badge tone="info">{t(`market.shipment_step.${s.status}`)}</Badge>
                  </div>
                  <ShipmentTimeline status={s.status} />
                  <div className="flex flex-wrap gap-x-5 gap-y-1 text-label text-ink-muted">
                    {s.planned_distance_km != null && (
                      <span>{t('market.distance_label')}: {number(Math.round(s.planned_distance_km))} km</span>
                    )}
                    {s.eta_at && <span>{t('market.eta')}: {date(s.eta_at)}</span>}
                    <span className="tnum">{money(s.earnings_paise)}</span>
                  </div>
                </Card>
              ))}
            </div>
          )}
      </section>
    </div>
  );
}
