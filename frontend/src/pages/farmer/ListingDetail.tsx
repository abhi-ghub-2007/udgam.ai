import { useNavigate, useParams } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { useDeleteListing, useProduct } from '@/hooks/queries';
import {
  Badge, Button, Card, CardSkeleton, CardTitle, ErrorState, LinkButton, PageHeader,
} from '@/components/ui';
import { money, number, date } from '@/utils/format';

export default function ListingDetail() {
  const { id } = useParams();
  const { t } = useTranslation();
  const navigate = useNavigate();
  const q = useProduct(id);
  const del = useDeleteListing();

  if (q.isLoading) return <CardSkeleton lines={5} />;
  if (q.isError || !q.data) {
    return <ErrorState title={t('common.error_title')} body={t('common.error_body')}
                       retryLabel={t('common.retry')} onRetry={() => void q.refetch()} />;
  }
  const p = q.data;

  const onDelete = async () => {
    await del.mutateAsync(p.id);
    navigate('/farmer/listings', { replace: true });
  };

  return (
    <div className="space-y-6">
      <PageHeader
        title={p.crop_name ?? t('market.detail_title')}
        actions={<LinkButton to="/farmer/decisions" variant="outline">{t('decide.title')}</LinkButton>}
      />
      <Card className="space-y-4 max-w-2xl">
        <div className="flex flex-wrap items-center gap-2">
          <Badge tone={p.status === 'active' ? 'success' : 'neutral'}>{p.status}</Badge>
          {p.grade && <Badge tone="info">{t('product.grade')} {p.grade}</Badge>}
          {p.grade_method && <Badge tone="insight">{t(`ai.method_${p.grade_method}`)}</Badge>}
        </div>

        <p className="tnum text-display font-bold text-primary">
          {money(p.asking_price_paise)}
          <span className="ml-1 text-body font-normal text-ink-muted">{t('common.per_kg')}</span>
        </p>

        <dl className="grid gap-3 sm:grid-cols-2">
          <div>
            <dt className="text-label text-ink-muted">{t('market.available')}</dt>
            <dd className="tnum text-body font-semibold">{number(p.available_quantity_kg)} {t('common.kg')}</dd>
          </div>
          <div>
            <dt className="text-label text-ink-muted">{t('market.quantity_kg')}</dt>
            <dd className="tnum text-body font-semibold">{number(p.quantity_kg)} {t('common.kg')}</dd>
          </div>
          {p.district && (
            <div>
              <dt className="text-label text-ink-muted">{t('auth.district')}</dt>
              <dd className="text-body font-semibold">{p.district}</dd>
            </div>
          )}
          {p.harvest_date && (
            <div>
              <dt className="text-label text-ink-muted">{t('market.harvest_date')}</dt>
              <dd className="text-body font-semibold">{date(p.harvest_date)}</dd>
            </div>
          )}
        </dl>

        {p.description && (
          <div>
            <CardTitle className="text-body">{t('market.description')}</CardTitle>
            <p className="mt-1 text-body text-ink-muted">{p.description}</p>
          </div>
        )}

        <div className="flex flex-wrap gap-3 border-t border-line-card pt-4">
          <Button variant="danger" onClick={onDelete} loading={del.isPending}>
            {t('common.delete')}
          </Button>
          <Button variant="outline" onClick={() => navigate(-1)}>{t('common.back')}</Button>
        </div>
      </Card>
    </div>
  );
}
