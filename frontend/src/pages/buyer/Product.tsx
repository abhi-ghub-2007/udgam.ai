import { useNavigate, useParams } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { useProduct } from '@/hooks/queries';
import { Badge, Button, Card, CardSkeleton, ErrorState, PageHeader } from '@/components/ui';
import { money, number, date } from '@/utils/format';

export default function BuyerProduct() {
  const { id } = useParams();
  const { t } = useTranslation();
  const navigate = useNavigate();
  const q = useProduct(id);

  if (q.isLoading) return <CardSkeleton lines={5} />;
  if (q.isError || !q.data) {
    return (
      <ErrorState
        title={t('common.error_title')} body={t('common.error_body')}
        retryLabel={t('common.retry')} onRetry={() => void q.refetch()}
      />
    );
  }
  const p = q.data;
  const total = p.available_quantity_kg * p.asking_price_paise;

  return (
    <div className="space-y-6">
      <PageHeader title={p.crop_name ?? t('market.detail_title')} />
      <Card className="max-w-2xl space-y-4">
        <div className="flex flex-wrap items-center gap-2">
          {p.grade && <Badge tone="info">{t('product.grade')} {p.grade}</Badge>}
          {p.grade_method && <Badge tone="insight">{t(`ai.method_${p.grade_method}`)}</Badge>}
          {p.district && <Badge>{p.district}</Badge>}
        </div>

        <p className="tnum text-display font-bold text-primary">
          {money(p.asking_price_paise)}
          <span className="ml-1 text-body font-normal text-ink-muted">{t('common.per_kg')}</span>
        </p>

        <dl className="grid gap-3 sm:grid-cols-2">
          <div>
            <dt className="text-label text-ink-muted">{t('market.available')}</dt>
            <dd className="tnum text-body font-semibold">
              {number(p.available_quantity_kg)} {t('common.kg')}
            </dd>
          </div>
          <div>
            <dt className="text-label text-ink-muted">{t('market.total_value')}</dt>
            <dd className="tnum text-body font-semibold">{money(total)}</dd>
          </div>
          {p.harvest_date && (
            <div>
              <dt className="text-label text-ink-muted">{t('market.harvest_date')}</dt>
              <dd className="text-body font-semibold">{date(p.harvest_date)}</dd>
            </div>
          )}
          {p.farmer_name && (
            <div>
              <dt className="text-label text-ink-muted">{t('market.farmer_label')}</dt>
              <dd className="text-body font-semibold">{p.farmer_name}</dd>
            </div>
          )}
        </dl>

        {p.description && <p className="text-body text-ink-muted">{p.description}</p>}

        <Button variant="outline" onClick={() => navigate(-1)}>{t('common.back')}</Button>
      </Card>
    </div>
  );
}
