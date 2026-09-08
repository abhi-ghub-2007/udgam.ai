/**
 * Help & Grievances -- the dashboard.
 *
 * One screen for all three roles. A farmer, a buyer and a transporter have
 * genuinely different jobs, but "something went wrong with a transaction I am
 * part of" is the same job, and splitting it into three pages would have meant
 * three places for the rules to drift apart.
 *
 * The counts are plain arithmetic over rows the server returned. Nothing here
 * is estimated, modelled or rounded up.
 */
import { Link } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { useGrievances } from '@/hooks/queries';
import {
  Card, CardSkeleton, EmptyState, ErrorState, LinkButton, PageHeader, StatCard,
} from '@/components/ui';
import { GrievanceStatusBadge } from '@/components/grievance/GrievanceBits';
import { dateTime } from '@/utils/format';

export default function Grievances() {
  const { t } = useTranslation();
  const { data, isLoading, isError, refetch } = useGrievances();

  return (
    <div className="space-y-6">
      <PageHeader
        title={t('grievance.title')}
        subtitle={t('grievance.subtitle')}
        actions={<LinkButton to="/help/new">{t('grievance.report_issue')}</LinkButton>}
      />

      {isLoading && <CardSkeleton lines={4} />}

      {isError && (
        <ErrorState
          title={t('common.error_title')}
          body={t('common.error_body')}
          onRetry={() => void refetch()}
          retryLabel={t('common.retry')}
        />
      )}

      {data && (
        <>
          <div className="grid gap-4 sm:grid-cols-3">
            <StatCard label={t('grievance.stat_open')} value={String(data.summary.open)} />
            <StatCard label={t('grievance.stat_resolved')} value={String(data.summary.resolved)} />
            <StatCard label={t('grievance.stat_total')} value={String(data.summary.total)} />
          </div>

          {data.cases.length === 0 ? (
            <EmptyState
              title={t('grievance.empty_title')}
              body={t('grievance.empty_body')}
              action={<LinkButton to="/help/new">{t('grievance.report_issue')}</LinkButton>}
            />
          ) : (
            <ul className="space-y-3">
              {data.cases.map((c) => (
                <li key={c.id}>
                  <Card as="article" className="space-y-2">
                    <Link to={`/help/${c.id}`} className="block space-y-2">
                      <div className="flex flex-wrap items-center justify-between gap-2">
                        {/* The case number leads: it is the thing a user
                            quotes when they talk about their problem. */}
                        <span className="font-mono text-label font-semibold text-ink">
                          {c.case_number}
                        </span>
                        <GrievanceStatusBadge status={c.status} />
                      </div>

                      <p className="text-body font-medium text-ink">
                        {t(`grievance.sub_${c.subcategory}`)}
                      </p>

                      <p className="text-label text-ink-muted">
                        {/* Which side you are on, stated plainly. Seeing a case
                            "against" you in the same list as ones you raised,
                            with no marking, would be alarming and unclear. */}
                        {c.my_party === 'respondent'
                          ? t('grievance.role_respondent')
                          : t('grievance.role_complainant')}
                        {c.order_no ? ` · ${c.order_no}` : ''}
                        {' · '}{dateTime(c.created_at)}
                      </p>
                    </Link>
                  </Card>
                </li>
              ))}
            </ul>
          )}
        </>
      )}
    </div>
  );
}
