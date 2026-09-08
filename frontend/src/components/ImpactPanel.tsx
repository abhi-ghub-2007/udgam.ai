/**
 * What has actually moved through UDGAM.
 *
 * WHY EVERY NUMBER HERE IS A COUNT
 * --------------------------------
 * The temptation on a slide is "farmers earn 23% more". We cannot show that:
 * `orders.traditional_chain_price_paise` is never populated anywhere in the
 * codebase, so any such figure would be invented. What CAN be counted honestly
 * is what the database already holds -- orders fulfilled, kilograms moved,
 * what farmers were paid, and what share of the buyer's money reached them.
 *
 * The farmer-share figure is the one that carries the argument, and it is
 * arithmetic on two stored columns rather than a claim: payout over payout plus
 * platform fee. A visitor can check it against any order's own breakdown.
 *
 * The demo-data note is not a disclaimer bolted on afterwards. The database
 * carries seeded demonstration orders next to real ones, and presenting their
 * sum as real-world impact without saying so would be the exact fabrication
 * the rest of the product refuses to make.
 */
import { useTranslation } from 'react-i18next';
import { useQuery } from '@tanstack/react-query';
import { api } from '@/services/api/client';
import { Card, CardTitle, StatCard } from '@/components/ui';
import { money, number } from '@/utils/format';

interface Impact {
  orders_fulfilled: number;
  produce_moved_kg: number;
  farmer_payout_paise: number;
  platform_fee_paise: number;
  farmer_share_pct: number | null;
  farmers: number;
  buyers: number;
  transporters: number;
  deliveries_completed: number;
  method: string;
  includes_demo_data: boolean;
}

export function ImpactPanel() {
  const { t } = useTranslation();
  const { data } = useQuery({
    queryKey: ['impact'],
    queryFn: () => api.get<Impact>('/api/dashboard/impact'),
    staleTime: 5 * 60_000,
  });

  // No skeleton and no error state: this is context, not the reason anyone
  // opened the page. If it cannot load, the dashboard is simply one card
  // shorter rather than showing a farmer an error about something they did
  // not ask for.
  if (!data) return null;

  return (
    <Card as="section" className="space-y-4">
      <CardTitle>{t('impact.title')}</CardTitle>

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard label={t('impact.orders')} value={number(data.orders_fulfilled)} />
        <StatCard label={t('impact.produce')} value={`${number(data.produce_moved_kg)} ${t('common.kg')}`} />
        <StatCard label={t('impact.payout')} value={money(data.farmer_payout_paise, { compact: true })} />
        {data.farmer_share_pct !== null && (
          <StatCard
            label={t('impact.share')}
            value={`${data.farmer_share_pct}%`}
            note={t('impact.share_note')}
            tone="primary"
          />
        )}
      </div>

      <p className="text-label text-ink-muted">
        {t('impact.participants', {
          farmers: data.farmers, buyers: data.buyers,
          transporters: data.transporters, deliveries: data.deliveries_completed,
        })}
      </p>

      {/* Stated, not hidden. */}
      {data.includes_demo_data && (
        <p className="text-label text-ink-muted">{t('impact.demo_note')}</p>
      )}
    </Card>
  );
}
