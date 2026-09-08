import { useNavigate, useParams } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { useOrder } from '@/hooks/queries';
import { Badge, Button, Card, CardSkeleton, ErrorState, PageHeader } from '@/components/ui';
import { ReportIssueButton } from '@/components/grievance/GrievanceBits';
import { money, number, date } from '@/utils/format';

export default function JobDetail() {
  const { id } = useParams();
  const { t } = useTranslation();
  const navigate = useNavigate();
  const q = useOrder(id);

  if (q.isLoading) return <CardSkeleton lines={5} />;
  if (q.isError || !q.data) {
    return (
      <ErrorState
        title={t('common.error_title')} body={t('common.error_body')}
        retryLabel={t('common.retry')} onRetry={() => void q.refetch()}
      />
    );
  }
  const o = q.data;

  return (
    <div className="space-y-6">
      <PageHeader
        title={o.order_no}
        subtitle={t('transporter.job_details')}
        actions={<ReportIssueButton orderId={o.id} />}
      />
      <Card className="max-w-2xl space-y-4">
        <Badge tone="info">{t(`order.status.${o.status}`)}</Badge>

        <dl className="grid gap-3 sm:grid-cols-2">
          <div>
            <dt className="text-label text-ink-muted">{t('transporter.cargo_value')}</dt>
            <dd className="tnum text-h2 font-bold text-primary">{money(o.subtotal_paise)}</dd>
          </div>
          {o.needed_by && (
            <div>
              <dt className="text-label text-ink-muted">{t('market.needed_by')}</dt>
              <dd className="text-body font-semibold">{date(o.needed_by)}</dd>
            </div>
          )}
        </dl>

        {o.items?.length > 0 && (
          <ul className="space-y-1 border-t border-line-card pt-4">
            {o.items.map((it, i) => (
              <li key={i} className="flex justify-between gap-3 text-body">
                <span>{it.crop_name ?? t('market.produce')}</span>
                <span className="tnum">{number(it.quantity_kg)} {t('common.kg')}</span>
              </li>
            ))}
          </ul>
        )}

        <p className="rounded-md bg-surface-low px-3 py-2 text-label text-ink-muted">
          {t('transporter.available_after_accept')}
        </p>

        <Button variant="outline" onClick={() => navigate(-1)}>{t('common.back')}</Button>
      </Card>
    </div>
  );
}
