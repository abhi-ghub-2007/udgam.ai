/**
 * Route optimisation. The optimiser itself is backend
 * (services/route_optimizer.py, exposed at GET /api/transport/optimize) --
 * this page requests a plan and visualises the result. No routing maths runs
 * in the browser.
 *
 * The map is loaded lazily: Leaflet is ~150KB and only this page needs it, so
 * it must never land in the initial bundle.
 */
import { Suspense, lazy, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useQuery } from '@tanstack/react-query';
import { api } from '@/services/api/client';
import {
  Badge, Button, Card, CardSkeleton, CardTitle, EmptyState, ErrorState,
  PageHeader, Skeleton,
} from '@/components/ui';
import { MethodBadge } from '@/components/ui/Provenance';
import { number } from '@/utils/format';

const RouteMap = lazy(() => import('@/components/maps/RouteMap'));

interface Stop { lat: number; lon: number; label?: string | null }
interface OptimizeResponse {
  stops?: Stop[];
  naive_distance_km?: number;
  optimized_distance_km?: number;
  distance_saved_pct?: number;
  method?: 'ALGORITHMIC' | 'HEURISTIC' | 'REAL' | 'SYNTHETIC';
  solver?: string | null;
  message?: string;
}

export default function RoutesPage() {
  const { t } = useTranslation();
  const [showMap, setShowMap] = useState(false);

  const q = useQuery({
    queryKey: ['transport', 'optimize'],
    queryFn: () => api.get<OptimizeResponse>('/api/transport/optimize'),
  });

  return (
    <div className="space-y-6">
      <PageHeader title={t('transporter.optimized_route')} />

      {q.isLoading ? <CardSkeleton lines={4} />
        : q.isError ? (
          <ErrorState
            title={t('common.error_title')} body={t('common.error_body')}
            retryLabel={t('common.retry')} onRetry={() => void q.refetch()}
          />
        ) : !q.data || !(q.data.stops?.length) ? (
          <EmptyState title={t('market.transport_none_title')} body={q.data?.message} />
        ) : (
          <Card className="space-y-5">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <CardTitle>{t('transporter.optimized_route')}</CardTitle>
              <div className="flex items-center gap-2">
                <MethodBadge method={q.data.method ?? 'ALGORITHMIC'} />
                {q.data.solver && <Badge>{q.data.solver}</Badge>}
              </div>
            </div>

            <div className="grid gap-4 sm:grid-cols-3">
              <div>
                <p className="text-label text-ink-muted">{t('market.distance_label')}</p>
                <p className="tnum text-stat font-bold text-ink">
                  {number(Math.round(q.data.optimized_distance_km ?? 0))} km
                </p>
              </div>
              <div>
                <p className="text-label text-ink-muted">{t('transporter.route_plan')}</p>
                <p className="tnum text-stat font-bold text-ink-muted line-through">
                  {number(Math.round(q.data.naive_distance_km ?? 0))} km
                </p>
              </div>
              <div>
                <p className="text-label text-ink-muted">{t('landing.stat_route_saving')}</p>
                <p className="tnum text-stat font-bold text-primary">
                  {(q.data.distance_saved_pct ?? 0).toFixed(1)}%
                </p>
              </div>
            </div>

            {/* Leaflet only downloads once the user asks for the map. */}
            {showMap ? (
              <Suspense fallback={<Skeleton className="h-72 w-full" />}>
                <RouteMap stops={q.data.stops!} />
              </Suspense>
            ) : (
              <Button variant="outline" onClick={() => setShowMap(true)}>
                {t('transporter.optimized_route')}
              </Button>
            )}
          </Card>
        )}
    </div>
  );
}
