import { useTranslation } from 'react-i18next';
import { useMyListings } from '@/hooks/queries';
import { CardSkeleton, EmptyState, ErrorState, LinkButton, PageHeader } from '@/components/ui';
import { ProductCard } from '@/components/ProductCard';

export default function Listings() {
  const { t } = useTranslation();
  const q = useMyListings();

  return (
    <div className="space-y-6">
      <PageHeader
        title={t('market.my_listings_title')}
        actions={<LinkButton to="/farmer/listings/new">{t('market.list_new')}</LinkButton>}
      />
      {q.isLoading ? (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {Array.from({ length: 3 }).map((_, i) => <CardSkeleton key={i} lines={2} />)}
        </div>
      ) : q.isError ? (
        <ErrorState title={t('common.error_title')} body={t('common.error_body')}
                    retryLabel={t('common.retry')} onRetry={() => void q.refetch()} />
      ) : (q.data ?? []).length === 0 ? (
        <EmptyState
          title={t('market.empty_listings')}
          action={<LinkButton to="/farmer/listings/new">{t('market.list_new')}</LinkButton>}
        />
      ) : (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {q.data!.map((p) => (
            <ProductCard key={p.id} product={p} to={`/farmer/listings/${p.id}`} />
          ))}
        </div>
      )}
    </div>
  );
}
