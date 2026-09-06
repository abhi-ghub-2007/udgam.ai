import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useCrops, useMarketplace } from '@/hooks/queries';
import { Card, CardSkeleton, EmptyState, ErrorState, Field, PageHeader, Select } from '@/components/ui';
import { ProductCard } from '@/components/ProductCard';

export default function Market() {
  const { t, i18n } = useTranslation();
  const crops = useCrops();
  const [cropId, setCropId] = useState('');
  const [grade, setGrade] = useState('');
  const q = useMarketplace({ crop_id: cropId || undefined, grade: grade || undefined });

  const cropName = (c: { name_en: string; name_hi: string; name_mr: string }) =>
    i18n.language === 'hi' ? c.name_hi : i18n.language === 'mr' ? c.name_mr : c.name_en;

  return (
    <div className="space-y-6">
      <PageHeader title={t('market.browse_title')} />

      {/* Two filters, not twenty: the page should not become a control panel. */}
      <Card className="grid gap-4 sm:grid-cols-2 lg:max-w-xl">
        <Field label={t('market.crop')} htmlFor="f-crop">
          <Select id="f-crop" value={cropId} onChange={(e) => setCropId(e.target.value)}>
            <option value="">{t('market.all_crops')}</option>
            {(crops.data ?? []).map((c) => (
              <option key={c.id} value={c.id}>{cropName(c)}</option>
            ))}
          </Select>
        </Field>
        <Field label={t('market.min_grade')} htmlFor="f-grade">
          <Select id="f-grade" value={grade} onChange={(e) => setGrade(e.target.value)}>
            <option value="">{t('market.any_grade')}</option>
            {['A', 'B', 'C'].map((g) => <option key={g} value={g}>{g}</option>)}
          </Select>
        </Field>
      </Card>

      {q.isLoading ? (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {Array.from({ length: 6 }).map((_, i) => <CardSkeleton key={i} lines={2} />)}
        </div>
      ) : q.isError ? (
        <ErrorState
          title={t('common.error_title')} body={t('common.error_body')}
          retryLabel={t('common.retry')} onRetry={() => void q.refetch()}
        />
      ) : (q.data ?? []).length === 0 ? (
        <EmptyState title={t('market.no_matches')} />
      ) : (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {q.data!.map((p) => (
            <ProductCard key={p.id} product={p} to={`/buyer/product/${p.id}`} />
          ))}
        </div>
      )}
    </div>
  );
}
