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
      {/* Rows open the shared order page, where the farmer accepts or declines
          and arranges transport when the order says they are the one to. */}
      <OrderList orders={q.data} loading={q.isLoading} error={q.isError}
                 onRetry={() => void q.refetch()} side="farmer"
                 linkTo={(o) => `/farmer/orders/${o.id}`} />
    </div>
  );
}
