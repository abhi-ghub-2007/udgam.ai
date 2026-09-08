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
  Aggregation, BuyerDashboard, Capacity, Crop, DemandHorizonForecast,
  Credential, FarmerDashboard, ForecastHorizon, ForecastSummary,
  GradeResult, Grievance, GrievanceDetail, GrievanceEvidence, GrievanceList,
  GrievanceMessage, GrievanceTaxonomy,
  MarketCompare, MatchesResponse, NetExitResponse, NotificationsResponse, Order,
  OrderFeedbackState, OrderStatus, Product, ProfileReviews, BuyerRequest, Review,
  SaleWindowResponse, Shipment, ShipmentDetails, TransportJob,
  VerificationMe, VerificationProgress,
  TransportOptionsResponse, TransporterDashboard,
} from '@/types/api';

/* ------------------------------------------------------------- reference */
export const useCrops = () =>
  useQuery({
    queryKey: ['crops'],
    // Reference data: effectively immutable for a session.
    staleTime: 60 * 60_000,
    // GET /api/crops (routers/profiles.py) returns {"items": [...]}, not
    // {"crops": [...]} -- this was read wrong during the migration, which
    // silently left the crop dropdown empty on every form that uses it.
    queryFn: () => api.get<{ items: Crop[] }>('/api/crops').then((r) => r.items ?? []),
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
    // GET /api/products/{id} (routers/products.py) returns
    // {"product": {...}, "quality_grade": {...}, "farmer": {...}}, not a bare
    // Product -- reading the envelope as the product left every field
    // (price, quantity, grade) undefined on the listing detail page.
    queryFn: () => api.get<{ product: Product }>(`/api/products/${id}`).then((r) => r.product),
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

/**
 * AI-1: uploads a photo for an EXISTING listing and runs the grading heuristic
 * server-side. The grade is never computed in the browser -- this call is the
 * only way a product acquires a grade.
 */
export function useGradePhoto() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ productId, file }: { productId: string; file: File }) => {
      const body = new FormData();
      body.append('file', file);
      return api.postForm<GradeResult>(`/api/products/${productId}/photo`, body);
    },
    onSuccess: (_result, { productId }) => {
      void qc.invalidateQueries({ queryKey: ['products'] });
      void qc.invalidateQueries({ queryKey: ['products', productId] });
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
type OrderEnvelope = {
  order: Order; items: Order['items']; farmer: Order['farmer']; buyer: Order['buyer'];
  /** Present once transport has been planned; null before that. */
  shipment: ShipmentDetails | null;
};

// GET /api/orders/{id} and POST /api/orders (routers/orders.py get_order /
// create_order -- the latter returns the former) both return
// {"order": {...}, "items": [...], "farmer": {...}, "buyer": {...}, ...},
// a different shape from the list endpoint, which already flattens
// items/counterparty onto each row. Reading the envelope as the Order itself
// left every field (status, order_no, items) undefined.
const unwrapOrder = (r: OrderEnvelope): Order => ({
  ...r.order, items: r.items ?? [], farmer: r.farmer, buyer: r.buyer,
  shipment: r.shipment ?? null,
});

export const useOrders = () =>
  useQuery({
    queryKey: ['orders'],
    queryFn: () => api.get<{ orders: Order[] }>('/api/orders').then((r) => r.orders ?? []),
  });

export const useOrder = (id: string | undefined) =>
  useQuery({
    queryKey: ['orders', id],
    enabled: Boolean(id),
    queryFn: () => api.get<OrderEnvelope>(`/api/orders/${id}`).then(unwrapOrder),
  });

/**
 * B-2: places an order against a listing (POST /api/orders,
 * routers/orders.py create_order). The backend derives the price from the
 * listing's authoritative asking_price_paise and re-validates quantity
 * against what is actually still available -- the frontend never sends a
 * price and must treat any total it shows before submitting as an estimate.
 */
export function useCreateOrder() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: {
      product_id: string;
      farmer_id: string;
      quantity_kg: number;
      logistics_arranged_by: 'buyer' | 'farmer';
      delivery_pincode?: string | null;
      needed_by?: string | null;
      notes?: string | null;
    }) => api.post<OrderEnvelope>('/api/orders', body).then(unwrapOrder),
    onSuccess: (order) => {
      void qc.invalidateQueries({ queryKey: ['orders'] });
      // The listing's available quantity just changed for every viewer.
      void qc.invalidateQueries({ queryKey: ['products'] });
      void qc.invalidateQueries({ queryKey: ['dashboard', 'buyer'] });
      void qc.invalidateQueries({ queryKey: ['dashboard', 'farmer'] });
      qc.setQueryData(['orders', order.id], order);
    },
  });
}

/* ------------------------------------------------------------- transport */
/** Move an order along the state machine (accept, decline, cancel, close).
    The server re-checks that this role is allowed to make this move, so a
    button appearing is never what authorises it. */
/** ACCEPTED -> PAYMENT_HELD. Mock provider (there is no real payment rail
    yet), but this call is what actually exists for it -- nothing before this
    fix gave the buyer a way to trigger it, so every order dead-ended here. */
export function usePayOrder(orderId: string | undefined) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => api.post<unknown>(`/api/orders/${orderId}/pay`, {}),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ['orders'] });
      void qc.invalidateQueries({ queryKey: ['dashboard'] });
    },
  });
}

/** assigned -> picked_up -> in_transit -> delivered. Each shipment status
    change also advances the order's own status (transport.py
    update_shipment_status), which is what eventually unlocks reviews. */
export function useUpdateShipmentStatus(shipmentId: string | undefined) {
  const qc = useQueryClient();
  return useMutation({
    // 'delivered' is no longer accepted here -- the backend rejects it. Only
    // the buyer's own confirm-delivery call (useConfirmDelivery) can set it.
    mutationFn: (status: 'picked_up' | 'in_transit' | 'arrived') =>
      api.post<{ ok: boolean; status: string }>(`/api/shipments/${shipmentId}/status`, { status }),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ['shipments'] });
      void qc.invalidateQueries({ queryKey: ['orders'] });
      void qc.invalidateQueries({ queryKey: ['dashboard'] });
    },
  });
}

/** Farmer says the produce is ready and handed over. Gates the transporter's
    own ability to mark 'picked_up' (§3). */
export function useConfirmPickup(shipmentId: string | undefined) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => api.post<{ ok: boolean }>(`/api/shipments/${shipmentId}/confirm-pickup`, {}),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ['shipments'] });
      void qc.invalidateQueries({ queryKey: ['orders'] });
    },
  });
}

/** Buyer says the goods actually arrived (§13) -- the only path to
    shipment status 'delivered' and order status DELIVERED. */
export function useConfirmDelivery(shipmentId: string | undefined) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => api.post<{ ok: boolean }>(`/api/shipments/${shipmentId}/confirm-delivery`, {}),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ['shipments'] });
      void qc.invalidateQueries({ queryKey: ['orders'] });
      void qc.invalidateQueries({ queryKey: ['dashboard'] });
    },
  });
}

export interface ShipmentCheckpoint {
  code: 'created' | 'pickup_confirmed' | 'journey_started' | 'near_destination' | 'arrived' | 'delivered';
  at: string | null;
  done: boolean;
}

/** Real timestamps, not fake frontend states (§11). */
export const useShipmentCheckpoints = (shipmentId: string | undefined) =>
  useQuery({
    queryKey: ['shipments', 'checkpoints', shipmentId],
    enabled: Boolean(shipmentId),
    queryFn: () => api.get<{ shipment_id: string; status: string; checkpoints: ShipmentCheckpoint[] }>(
      `/api/shipments/${shipmentId}/checkpoints`,
    ),
  });

export function useOrderTransition(orderId: string | undefined) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ to, note }: { to: OrderStatus; note?: string }) =>
      api.post<unknown>(`/api/orders/${orderId}/transition`, { to_status: to, note }),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ['orders'] });
      void qc.invalidateQueries({ queryKey: ['feedback', orderId] });
      void qc.invalidateQueries({ queryKey: ['dashboard'] });
    },
  });
}

/* ------------------------------------------------- transport offers (F-7/T-7) */
/** Offers waiting on this transporter, each carrying the pickup, drop, window,
    deadline, weight and price they need to answer yes or no. */
export const useTransportJobs = () =>
  useQuery({
    queryKey: ['transport', 'jobs'],
    queryFn: () => api.get<{ jobs: TransportJob[] }>('/api/transport/jobs').then((r) => r.jobs ?? []),
  });

/** Carriers that could actually take this shipment. Ordered by cost then
    distance server-side; reliability comes along to inform, not to rank. */
export const useTransportOptions = (orderId: string | undefined, enabled = true) =>
  useQuery({
    queryKey: ['transport', 'options', orderId],
    enabled: Boolean(orderId) && enabled,
    queryFn: () => api.get<TransportOptionsResponse>(`/api/orders/${orderId}/transport-options`),
  });

export function useSaveShipmentDetails(orderId: string | undefined) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: Record<string, unknown>) =>
      api.put<{ shipment: ShipmentDetails }>(`/api/orders/${orderId}/shipment`, body)
        .then((r) => r.shipment),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ['orders', orderId] });
      void qc.invalidateQueries({ queryKey: ['transport', 'options', orderId] });
    },
  });
}

export function useSendTransportOffers(orderId: string | undefined) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (capacityIds: string[]) =>
      api.post<{ offers: unknown[]; skipped: Array<{ capacity_id: string; reason: string }> }>(
        `/api/orders/${orderId}/transport-offers`, { capacity_ids: capacityIds }),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ['transport', 'options', orderId] });
      void qc.invalidateQueries({ queryKey: ['orders', orderId] });
    },
  });
}

/** Accept is the one that races: two carriers can press it at the same moment,
    and the server settles it. A 409 here means somebody else won, which is a
    normal outcome to render, not an error to hide. */
export function useAnswerTransportOffer() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ offerId, answer, reason }:
                 { offerId: string; answer: 'accept' | 'decline'; reason?: string }) =>
      api.post<{ ok: boolean }>(`/api/transport/offers/${offerId}/${answer}`,
                                 answer === 'decline' ? { reason } : {}),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ['transport', 'jobs'] });
      void qc.invalidateQueries({ queryKey: ['shipments'] });
      void qc.invalidateQueries({ queryKey: ['dashboard', 'transporter'] });
    },
  });
}

/* ------------------------------------------------------------- reputation */
export const useProfileReviews = (profileId: string | undefined, role?: string) =>
  useQuery({
    queryKey: ['reviews', profileId, role ?? null],
    enabled: Boolean(profileId),
    queryFn: () => api.get<ProfileReviews>(`/api/profiles/${profileId}/reviews`,
                                            role ? { role } : undefined),
  });

/** What the caller may review on this order, and what they already said. */
export const useOrderFeedback = (orderId: string | undefined) =>
  useQuery({
    queryKey: ['feedback', orderId],
    enabled: Boolean(orderId),
    queryFn: () => api.get<OrderFeedbackState>(`/api/orders/${orderId}/feedback`),
  });

export function useLeaveFeedback(orderId: string | undefined) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: { ratee_id: string; rating: number; tags?: string[]; comment?: string }) =>
      api.post<{ feedback: Review }>(`/api/orders/${orderId}/feedback`, body),
    onSuccess: (_r, body) => {
      void qc.invalidateQueries({ queryKey: ['feedback', orderId] });
      void qc.invalidateQueries({ queryKey: ['reviews', body.ratee_id] });
    },
  });
}

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

/** 7-day price + demand outlook for one crop in one district.

    One request rather than two so the card cannot show a price forecast and a
    demand signal captured at different moments. `enabled` keeps it from firing
    until both keys exist -- the Decision Center renders before a listing is
    picked. */
export const useForecastSummary = (cropId: string | undefined, district: string | undefined) =>
  useQuery({
    queryKey: ['forecast', 'summary', cropId, district],
    enabled: Boolean(cropId && district),
    // A daily mandi forecast does not change between two clicks; refetching it
    // on every focus would be pure noise against the API.
    staleTime: 30 * 60_000,
    queryFn: () =>
      api.get<ForecastSummary>('/api/forecast/summary', {
        crop_id: cropId, district,
      }),
  });

/** Expected buyer demand for one crop over one horizon.

    Keyed on crop + horizon so switching tabs re-reads the cache instead of
    re-hitting the API, and switching crops does not show the previous crop's
    numbers. Demand history moves at the pace of orders, so a long staleTime is
    honest here rather than merely convenient. */
export const useDemandHorizon = (
  cropId: string | undefined,
  horizon: ForecastHorizon,
  district?: string | null,
) =>
  useQuery({
    queryKey: ['forecast', 'demand-horizon', cropId, horizon, district],
    enabled: Boolean(cropId),
    staleTime: 30 * 60_000,
    queryFn: () =>
      api.get<DemandHorizonForecast>('/api/forecast/demand/horizon', {
        crop_id: cropId, horizon, district: district ?? undefined,
      }),
  });

/* ------------------------------------------------- identity verification */

export const useMyVerification = () =>
  useQuery({
    queryKey: ['verification', 'me'],
    queryFn: () => api.get<VerificationMe>('/api/verification/me'),
  });

/** Submit or resubmit one credential.

    The raw value goes up once and is never stored; the server returns only the
    mask. Status is decided server-side, so nothing here can request one. */
export function useSubmitCredential() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: { doc_type: string; value: string; expires_on?: string }) =>
      api.post<{ credential: Credential; message: string | null;
                 progress: VerificationProgress }>('/api/verification/submit', body),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ['verification'] });
      // The account-level badge is derived from credentials, so refresh what
      // renders it rather than leaving a stale "unverified" on screen.
      void qc.invalidateQueries({ queryKey: ['auth', 'me'] });
    },
  });
}

export function useWithdrawCredential() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (docType: string) =>
      api.delete<{ ok: boolean; progress: VerificationProgress }>(
        `/api/verification/${docType}`),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ['verification'] });
      void qc.invalidateQueries({ queryKey: ['auth', 'me'] });
    },
  });
}

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

/* ------------------------------------------------------------ grievances */

/** What may be reported. Served by the backend so the two can never disagree
    -- a category the client offers but the server rejects is a dead end. */
export const useGrievanceTaxonomy = () =>
  useQuery({
    queryKey: ['grievances', 'taxonomy'],
    queryFn: () => api.get<GrievanceTaxonomy>('/api/grievances/taxonomy'),
    staleTime: 60 * 60_000,   // vocabulary, not data
  });

/** Every case the caller is a party to, either side. RLS decides which. */
export const useGrievances = () =>
  useQuery({
    queryKey: ['grievances', 'mine'],
    queryFn: () => api.get<GrievanceList>('/api/grievances'),
  });

export const useGrievance = (id: string | undefined) =>
  useQuery({
    queryKey: ['grievances', id],
    queryFn: () => api.get<GrievanceDetail>(`/api/grievances/${id}`),
    enabled: !!id,
  });

export function useCreateGrievance() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: {
      category: string; subcategory: string; description: string;
      related_order_id?: string | null;
    }) => api.post<{ case: Grievance }>('/api/grievances', body),
    onSuccess: () => void qc.invalidateQueries({ queryKey: ['grievances'] }),
  });
}

export function useGrievanceMessage(id: string | undefined) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (message: string) =>
      api.post<{ message: GrievanceMessage }>(`/api/grievances/${id}/messages`, { message }),
    onSuccess: () => void qc.invalidateQueries({ queryKey: ['grievances', id] }),
  });
}

/** Move the case. Sends an ACTION, never a status -- there is no request shape
    here that could carry one. */
export function useGrievanceAction(id: string | undefined) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: { action: string; resolution?: string; note?: string }) =>
      api.post<{ case: Grievance; available_actions: string[] }>(
        `/api/grievances/${id}/actions`, body),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ['grievances', id] });
      void qc.invalidateQueries({ queryKey: ['grievances', 'mine'] });
      void qc.invalidateQueries({ queryKey: ['notifications'] });
    },
  });
}

export function useUploadEvidence(id: string | undefined) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (file: File) => {
      const fd = new FormData();
      fd.append('file', file);
      return api.post<{ evidence: GrievanceEvidence }>(
        `/api/grievances/${id}/evidence`, fd);
    },
    onSuccess: () => void qc.invalidateQueries({ queryKey: ['grievances', id] }),
  });
}

/** Ask for a short-lived signed link to one file. Not a query: the link
    expires in minutes, so caching it would hand back a dead URL. */
export function useEvidenceLink(grievanceId: string | undefined) {
  return useMutation({
    mutationFn: (evidenceId: string) =>
      api.get<{ url: string; expires_in: number; file_type: string }>(
        `/api/grievances/${grievanceId}/evidence/${evidenceId}`),
  });
}
