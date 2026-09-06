import { useTranslation } from 'react-i18next';
import { useOrders } from '@/hooks/queries';
import { PageHeader } from '@/components/ui';
import { OrderList } from '@/components/OrderList';

export default function FarmerOrders() {
  const { t } = useTranslation();
  const q = useOrders();
  return (
    <div className="space-y-6">
      <PageHeader title={t('market.orders_title')} />
      <OrderList orders={q.data} loading={q.isLoading} error={q.isError}
                 onRetry={() => void q.refetch()} side="farmer" />
    </div>
  );
}
