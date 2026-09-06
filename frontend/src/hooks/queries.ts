/**
 * Server state. Every backend read goes through one of these hooks so caching,
 * loading and error handling are consistent and stated once.
 *
 * Query keys are structured [domain, ...params] so invalidation can be surgical
 * (invalidate ['products'] after a listing mutation, not the whole cache).
 *
 * IMPORTANT: these hooks are for SERVER state only. Local UI state (which tab
 * is open, what a user has typed) stays in React state -- putting it here would
 * be misusing the cache (master prompt 7).
 */
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { api } from '@/services/api/client';
import type {
  Aggregation, BuyerDashboard, Capacity, Crop, FarmerDashboard,
  MarketCompare, MatchesResponse, NetExitResponse, NotificationsResponse, Order,
  Product, BuyerRequest, SaleWindowResponse, Shipment, TransporterDashboard,
} from '@/types/api';

/* ------------------------------------------------------------- reference */
export const useCrops = () =>
  useQuery({
    queryKey: ['crops'],
    // Reference data: effectively immutable for a session.
    staleTime: 60 * 60_000,
    queryFn: () => api.get<{ crops: Crop[] }>('/api/crops').then((r) => r.crops ?? []),
  });

/* ------------------------------------------------------------ dashboards */
export const useFarmerDashboard = () =>
  useQuery({
    queryKey: ['dashboard', 'farmer'],
    queryFn: () => api.get<FarmerDashboard>('/api/dashboard/farmer'),
  });

export const useBuyerDashboard = () =>
  useQuery({
    queryKey: ['dashboard', 'buyer'],
    queryFn: () => api.get<BuyerDashboard>('/api/dashboard/buyer'),
  });

export const useTransporterDashboard = () =>
  useQuery({
    queryKey: ['dashboard', 'transporter'],
    queryFn: () => api.get<TransporterDashboard>('/api/dashboard/transporter'),
  });

/* -------------------------------------------------------------- products */
export const useMyListings = () =>
  useQuery({
    queryKey: ['products', 'mine'],
    queryFn: () => api.get<{ products: Product[] }>('/api/products/mine').then((r) => r.products ?? []),
  });

export const useMarketplace = (params?: Record<string, string | number | undefined>) =>
  useQuery({
    queryKey: ['products', 'browse', params ?? {}],
    queryFn: () => api.get<{ products: Product[] }>('/api/products', params).then((r) => r.products ?? []),
  });

export const useProduct = (id: string | undefined) =>
  useQuery({
    queryKey: ['products', id],
    enabled: Boolean(id),
    queryFn: () => api.get<Product>(`/api/products/${id}`),
  });

export function useCreateListing() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: Record<string, unknown>) => api.post<Product>('/api/products', body),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ['products'] });
      void qc.invalidateQueries({ queryKey: ['dashboard', 'farmer'] });
    },
  });
}

export function useDeleteListing() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => api.delete<null>(`/api/products/${id}`),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ['products'] });
      void qc.invalidateQueries({ queryKey: ['dashboard', 'farmer'] });
    },
  });
}

/* -------------------------------------------------------------- requests */
export const useMyRequests = () =>
  useQuery({
    queryKey: ['requests', 'mine'],
    queryFn: () => api.get<{ requests: BuyerRequest[] }>('/api/buyer-requests/mine').then((r) => r.requests ?? []),
  });

export function useCreateRequest() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: Record<string, unknown>) => api.post<BuyerRequest>('/api/buyer-requests', body),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ['requests'] });
      void qc.invalidateQueries({ queryKey: ['dashboard', 'buyer'] });
    },
  });
}

/* -------------------------------------------------------------- matching */
export const useMatchingBuyers = () =>
  useQuery({
    queryKey: ['matching', 'buyers'],
    queryFn: () => api.get<MatchesResponse>('/api/matching/buyers').then((r) => r.matches ?? []),
  });

export const useMatchingListings = () =>
  useQuery({
    queryKey: ['matching', 'listings'],
    queryFn: () => api.get<{ matches: Product[] }>('/api/matching/listings').then((r) => r.matches ?? []),
  });

/* ---------------------------------------------------------------- orders */
export const useOrders = () =>
  useQuery({
    queryKey: ['orders'],
    queryFn: () => api.get<{ orders: Order[] }>('/api/orders').then((r) => r.orders ?? []),
  });

export const useOrder = (id: string | undefined) =>
  useQuery({
    queryKey: ['orders', id],
    enabled: Boolean(id),
    queryFn: () => api.get<Order>(`/api/orders/${id}`),
  });

/* ------------------------------------------------------------- transport */
export const useShipments = () =>
  useQuery({
    queryKey: ['shipments'],
    queryFn: () => api.get<{ shipments: Shipment[] }>('/api/shipments').then((r) => r.shipments ?? []),
  });

export const useMyCapacity = () =>
  useQuery({
    queryKey: ['capacity', 'mine'],
    queryFn: () => api.get<{ capacity: Capacity[] }>('/api/transport/capacity/mine').then((r) => r.capacity ?? []),
  });

export const useTransportEarnings = () =>
  useQuery({
    queryKey: ['transport', 'earnings'],
    queryFn: () => api.get<Record<string, number>>('/api/transport/earnings'),
  });

export function usePostCapacity() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: Record<string, unknown>) => api.post<Capacity>('/api/transport/capacity', body),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ['capacity'] });
      void qc.invalidateQueries({ queryKey: ['dashboard', 'transporter'] });
    },
  });
}

/* ---------------------------------------------------------------- market */
export const useMarketCompare = (cropId: string | undefined, fromDistrict?: string | null) =>
  useQuery({
    queryKey: ['market', 'compare', cropId, fromDistrict],
    enabled: Boolean(cropId),
    queryFn: () =>
      api.get<MarketCompare>('/api/market/compare', {
        crop_id: cropId, from_district: fromDistrict ?? undefined,
      }),
  });

/* ------------------------------------------------------------- decisions */
export const useNetExit = (productId: string | undefined) =>
  useQuery({
    queryKey: ['decisions', 'net-exit', productId],
    enabled: Boolean(productId),
    queryFn: () => api.get<NetExitResponse>('/api/decisions/net-exit', { product_id: productId }),
  });

export const useSaleWindow = (productId: string | undefined) =>
  useQuery({
    queryKey: ['decisions', 'sale-window', productId],
    enabled: Boolean(productId),
    queryFn: () => api.get<SaleWindowResponse>('/api/decisions/sale-window', { product_id: productId }),
  });

/* --------------------------------------------------------- notifications */
export const useNotifications = () =>
  useQuery({
    queryKey: ['notifications'],
    queryFn: () => api.get<NotificationsResponse>('/api/notifications'),
  });

export function useMarkRead() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => api.post<{ ok: boolean }>(`/api/notifications/${id}/read`, {}),
    onSuccess: () => void qc.invalidateQueries({ queryKey: ['notifications'] }),
  });
}

export function useMarkAllRead() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => api.post<{ ok: boolean }>('/api/notifications/read-all', {}),
    onSuccess: () => void qc.invalidateQueries({ queryKey: ['notifications'] }),
  });
}

/* ----------------------------------------------------------- aggregation */
export const useMyAggregations = () =>
  useQuery({
    queryKey: ['aggregations', 'mine'],
    queryFn: () => api.get<{ aggregations: Aggregation[] }>('/api/aggregations/mine').then((r) => r.aggregations ?? []),
  });

export const useAggregationInvitations = () =>
  useQuery({
    queryKey: ['aggregations', 'invitations'],
    queryFn: () =>
      api.get<{ invitations: unknown[] }>('/api/aggregations/invitations').then((r) => r.invitations ?? []),
  });

/* --------------------------------------------------------------- profile */
export function useUpdateProfile() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: Record<string, unknown>) => api.patch<unknown>('/api/profiles/me', body),
    onSuccess: () => void qc.invalidateQueries({ queryKey: ['profile'] }),
  });
}
