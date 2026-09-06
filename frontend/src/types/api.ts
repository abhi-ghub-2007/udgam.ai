/**
 * TypeScript models for the FastAPI contract.
 *
 * These describe what the backend ALREADY returns. They are written to match
 * `backend/app/routers/*.py` exactly -- if a shape here disagrees with the
 * backend, this file is wrong, not the backend. The API contract is frozen;
 * the frontend adapts to it (master prompt 6).
 */

export type Role = 'farmer' | 'buyer' | 'transporter';
export type Lang = 'en' | 'hi' | 'mr';
export type Grade = 'A' | 'B' | 'C';

/** Honesty labels. The UI must never present SYNTHETIC/ESTIMATED as REAL. */
export type MethodLabel = 'REAL' | 'SYNTHETIC' | 'ALGORITHMIC' | 'HEURISTIC';
export type Freshness = 'LIVE' | 'RECENT' | 'STALE' | 'ESTIMATED' | 'SYNTHETIC';

export type OrderStatus =
  | 'DRAFT' | 'PLACED' | 'ACCEPTED' | 'PAYMENT_HELD' | 'LOGISTICS_ASSIGNED'
  | 'PICKED_UP' | 'IN_TRANSIT' | 'DELIVERED' | 'CLOSED' | 'CANCELLED' | 'DISPUTED';

export type ProductStatus = 'draft' | 'active' | 'reserved' | 'sold' | 'withdrawn';
export type RequestStatus = 'open' | 'partially_fulfilled' | 'fulfilled' | 'cancelled' | 'expired';
export type ShipmentStatus = 'created' | 'assigned' | 'picked_up' | 'in_transit' | 'delivered' | 'cancelled';

// ---------------------------------------------------------------- auth
export interface AppConfig {
  supabase_url: string;
  supabase_anon_key: string;
  languages: Lang[];
  app_env: string;
  configured: boolean;
}

export interface Profile {
  id: string;
  role: Role;
  full_name: string | null;
  phone: string | null;
  email: string | null;
  district: string | null;
  state: string | null;
  pincode: string | null;
  preferred_language: Lang | null;
  avg_rating: number | null;
  rating_count: number | null;
  verification_status: string | null;
  is_storage_provider?: boolean;
  created_at?: string;
}

export interface MeResponse {
  profile: Profile;
  details: Record<string, unknown>;
  is_fpo: boolean;
}

// ---------------------------------------------------------------- crops
export interface Crop {
  id: string;
  code: string;
  name_en: string;
  name_hi: string;
  name_mr: string;
  category: string | null;
  default_shelf_life_days: number;
}

// ---------------------------------------------------------------- products
export interface Product {
  id: string;
  farmer_id: string;
  crop_id: string;
  crop_name?: string | null;
  crop_name_hi?: string | null;
  crop_name_mr?: string | null;
  quantity_kg: number;
  available_quantity_kg: number;
  asking_price_paise: number;
  grade: Grade | null;
  grade_confidence: number | null;
  grade_method: MethodLabel | null;
  harvest_date: string | null;
  available_until: string | null;
  status: ProductStatus;
  description: string | null;
  photo_path: string | null;
  district: string | null;
  farmer_name?: string | null;
  created_at: string;
}

export interface ProductsResponse { products: Product[] }

// ---------------------------------------------------------------- requests
export interface BuyerRequest {
  id: string;
  buyer_id: string;
  crop_id: string;
  crop_name?: string | null;
  quantity_kg: number;
  min_grade: Grade;
  target_price_paise: number | null;
  needed_by: string | null;
  delivery_district: string | null;
  delivery_pincode: string | null;
  status: RequestStatus;
  notes: string | null;
  match_count?: number;
  created_at: string;
}

export interface RequestsResponse { requests: BuyerRequest[] }

// ---------------------------------------------------------------- matching
export interface Match extends BuyerRequest {
  score: number;
  reasons: string[];
  buyer_name?: string | null;
}
export interface MatchesResponse { matches: Match[] }

// ---------------------------------------------------------------- dashboards
export interface FarmerDashboard {
  active_listings: number;
  active_orders: number;
  earnings_month_paise: number;
  listings: Product[];
  open_requests: BuyerRequest[];
}

export interface BuyerDashboard {
  active_orders: number;
  open_requests: number;
  saved_farmers: number;
  total_purchase_paise: number;
  recommended: Product[];
  requests: BuyerRequest[];
}

export interface TransporterDashboard {
  active_jobs: number;
  earnings_month_paise: number;
  total_earnings_paise: number;
  pending_consolidation: number;
  completed_deliveries: number;
  upcoming_pickups: Array<{
    id: string;
    order_no: string | null;
    order_status: OrderStatus | null;
    status: ShipmentStatus;
    eta_at: string | null;
    planned_distance_km: number | null;
    earnings_paise: number;
  }>;
  available_jobs: Array<{
    id: string;
    order_no: string;
    status: OrderStatus;
    subtotal_paise: number;
    needed_by: string | null;
  }>;
}

// ---------------------------------------------------------------- orders
export interface OrderItem {
  crop_id: string;
  crop_name?: string | null;
  quantity_kg: number;
  unit_price_paise: number;
  grade: Grade | null;
}

export interface Order {
  id: string;
  order_no: string;
  buyer_id: string;
  farmer_id: string | null;
  status: OrderStatus;
  subtotal_paise: number;
  buyer_total_paise: number;
  farmer_payout_paise: number;
  transport_cost_paise: number;
  platform_fee_paise: number;
  needed_by: string | null;
  placed_at: string | null;
  delivered_at: string | null;
  created_at: string;
  items: OrderItem[];
  counterparty: { full_name?: string | null; district?: string | null };
}

export interface OrdersResponse { orders: Order[] }

// ---------------------------------------------------------------- transport
export interface Shipment {
  id: string;
  order_id: string;
  order_no: string | null;
  order_status: OrderStatus | null;
  status: ShipmentStatus;
  planned_distance_km: number | null;
  actual_distance_km: number | null;
  eta_at: string | null;
  picked_up_at: string | null;
  delivered_at: string | null;
  earnings_paise: number;
}
export interface ShipmentsResponse { shipments: Shipment[] }

export interface Capacity {
  id: string;
  transporter_id: string;
  capacity_type: string;
  origin_district: string | null;
  dest_district: string | null;
  depart_at: string | null;
  total_capacity_kg: number;
  available_capacity_kg: number;
  price_paise_per_kg: number;
  price_paise_per_km: number;
  discount_pct: number;
  status: string;
  notes: string | null;
}
export interface CapacityResponse { capacity: Capacity[] }

// ---------------------------------------------------------------- market
export interface Provenance {
  source: string | null;
  updated_at: string | null;
  observed_for: string | null;
  freshness: Freshness;
  method: MethodLabel | null;
  confidence: number | null;
  is_synthetic: boolean;
  is_prediction: boolean;
}

export interface MarketRow {
  district: string;
  modal_price_paise: number;
  arrival_qty_tonnes: number | null;
  trend: { direction: 'rising' | 'falling' | 'steady' | 'unknown'; change_pct: number | null };
  distance_km: number | null;
  provenance: Provenance;
}

export interface MarketCompare {
  crop: Crop;
  from_district: string | null;
  availability: 'ok' | 'unavailable';
  ranked_by: string;
  markets: MarketRow[];
}

// ---------------------------------------------------------------- decisions
export interface CostLine {
  label: string;
  amount_paise: number;
  kind: 'gross' | 'deduction';
  borne_by: 'farmer' | 'buyer' | 'platform';
  basis: string;
  source: string | null;
  reduces_farmer_net: boolean;
}

export interface Opportunity {
  channel: 'direct_buyer' | 'mandi' | 'processor' | 'institutional';
  reference_id: string | null;
  reference_name: string | null;
  crop_code: string | null;
  grade: Grade | null;
  quantity_kg: number;
  unit_price_paise: number | null;
  gross_value_paise: number;
  transport_cost_paise: number | null;
  storage_cost_paise: number;
  platform_fee_paise: number;
  commission_paise: number;
  expected_loss_paise: number;
  net_realization_paise: number | null;
  risk_penalty_paise: number;
  risk_adjusted_paise: number | null;
  risk_notes: string[];
  advantage_over_next_paise: number | null;
  district: string | null;
  distance_km: number | null;
  holding_days: number;
  deadline: string | null;
  days_to_deadline: number | null;
  feasible: boolean;
  blockers: string[];
  cost_basis_complete: boolean;
  limitations: string[];
  payment_reliability: number | null;
  payment_reliability_basis: string | null;
  method: MethodLabel;
  price_provenance: Provenance | null;
  confidence: number | null;
  breakdown: CostLine[];
  reasons: string[];
}

export interface NeutralityDisclosure {
  ranked_by: string;
  factors: Record<string, string>;
  never_used: string[];
  statement: string;
  method: MethodLabel;
}

export interface NetExitResponse {
  product: {
    id: string; crop_code: string | null; crop_name: string | null;
    grade: Grade | null; quantity_kg: number; asking_price_paise: number | null;
    district: string | null;
  };
  holding_days: number;
  best: Opportunity | null;
  ranked: Opportunity[];
  excluded: Opportunity[];
  ranked_by: string;
  method: MethodLabel;
  assumptions: Record<string, unknown>;
  neutrality?: NeutralityDisclosure;
  availability: 'ok' | 'insufficient_data';
}

export interface SaleWindowResponse {
  product: {
    id: string; crop_code: string | null; crop_name: string | null;
    grade: Grade | null; quantity_kg: number; shelf_life_days: number | null;
  };
  district: string;
  recommendation: 'sell_now' | 'wait' | null;
  best: Opportunity | null;
  scenarios: Opportunity[];
  excluded: Opportunity[];
  ranked_by: string;
  method: MethodLabel;
  assumptions: Record<string, unknown>;
  neutrality?: NeutralityDisclosure;
  availability: 'ok' | 'insufficient_data';
}

// ---------------------------------------------------------------- notifications
export interface AppNotification {
  id: string;
  type: string;
  title_key: string;
  body_key: string;
  params: Record<string, string | number>;
  read_at: string | null;
  created_at: string;
}
export interface NotificationsResponse { items: AppNotification[]; unread_count: number }

// ---------------------------------------------------------------- aggregation
export interface AggregationItem {
  id: string;
  aggregation_id: string;
  product_id: string;
  farmer_id: string;
  quantity_kg: number;
  unit_price_paise: number;
  consent_status: 'suggested' | 'accepted' | 'rejected' | 'expired';
  consent_at: string | null;
}

export interface Aggregation {
  id: string;
  buyer_request_id: string;
  buyer_id: string;
  status: 'suggested' | 'accepted' | 'rejected' | 'expired';
  total_quantity_kg: number;
  combined_price_paise: number;
  grade_variance_warning: boolean;
  method: MethodLabel;
  items: AggregationItem[];
  accepted_kg?: number;
  awaiting_consent?: number;
}
