/**
 * Routing. Every one of the 29 legacy hash routes has an equivalent here, at
 * the same path minus the '#'. Nothing was dropped in the migration.
 *
 * SECURITY NOTE: RequireRole below is UX protection only -- it stops a farmer
 * seeing a buyer screen and getting a confusing error. The real boundary is
 * FastAPI's require_role dependency plus Postgres RLS, both of which
 * independently re-derive the caller's role from their JWT. Nothing here is
 * trusted server-side, and weakening it cannot escalate privileges.
 *
 * Every page is lazily imported, so a visitor to /login never downloads the
 * farmer dashboard, the decision engine views, Chart.js or Leaflet.
 */
import { lazy, type ReactNode } from 'react';
import { createBrowserRouter, Navigate, useLocation } from 'react-router-dom';
import { AppShell } from '@/components/layout/AppShell';
import { useAuth } from '@/services/auth/AuthProvider';
import { Skeleton } from '@/components/ui';
import type { Role } from '@/types/api';

const Landing = lazy(() => import('@/pages/auth/Landing'));
const Login = lazy(() => import('@/pages/auth/Login'));
const Signup = lazy(() => import('@/pages/auth/Signup'));
const Profile = lazy(() => import('@/pages/Profile'));
const Notifications = lazy(() => import('@/pages/Notifications'));

const FarmerHome = lazy(() => import('@/pages/farmer/Home'));
const FarmerListings = lazy(() => import('@/pages/farmer/Listings'));
const FarmerListingNew = lazy(() => import('@/pages/farmer/ListingNew'));
const FarmerListingDetail = lazy(() => import('@/pages/farmer/ListingDetail'));
const FarmerBuyers = lazy(() => import('@/pages/farmer/Buyers'));
const FarmerDecisions = lazy(() => import('@/pages/farmer/Decisions'));
const FarmerOrders = lazy(() => import('@/pages/farmer/Orders'));
const FarmerTransport = lazy(() => import('@/pages/farmer/Transport'));

const BuyerHome = lazy(() => import('@/pages/buyer/Home'));
const BuyerMarket = lazy(() => import('@/pages/buyer/Market'));
const BuyerProduct = lazy(() => import('@/pages/buyer/Product'));
const BuyerRequests = lazy(() => import('@/pages/buyer/Requests'));
const BuyerRequestNew = lazy(() => import('@/pages/buyer/RequestNew'));
const BuyerOrders = lazy(() => import('@/pages/buyer/Orders'));
const BuyerOrderTrack = lazy(() => import('@/pages/buyer/OrderTrack'));

const TransporterHome = lazy(() => import('@/pages/transporter/Home'));
const TransporterJobs = lazy(() => import('@/pages/transporter/Jobs'));
const TransporterJobDetail = lazy(() => import('@/pages/transporter/JobDetail'));
const TransporterCapacity = lazy(() => import('@/pages/transporter/Capacity'));
const TransporterCapacityNew = lazy(() => import('@/pages/transporter/CapacityNew'));
const TransporterRoutes = lazy(() => import('@/pages/transporter/Routes'));
const TransporterDeliveries = lazy(() => import('@/pages/transporter/Deliveries'));
const TransporterEarnings = lazy(() => import('@/pages/transporter/Earnings'));

const NotFound = lazy(() => import('@/pages/NotFound'));

function Booting() {
  return (
    <div className="mx-auto max-w-content space-y-4 p-6">
      <Skeleton className="h-8 w-48" />
      <Skeleton className="h-40" />
    </div>
  );
}

/** Requires a signed-in user; optionally a specific role. */
function RequireAuth({ role, children }: { role?: Role; children: ReactNode }) {
  const { signedIn, role: actual, loading } = useAuth();
  const location = useLocation();

  // Never redirect before the session has resolved, or a hard refresh on a
  // protected page would bounce a legitimately signed-in user to /login.
  if (loading) return <Booting />;
  if (!signedIn) return <Navigate to="/login" replace state={{ from: location.pathname }} />;
  if (role && actual !== role) return <Navigate to={actual ? `/${actual}` : '/'} replace />;
  return <>{children}</>;
}

/** Public pages bounce a signed-in user to their own dashboard. */
function PublicOnly({ children }: { children: ReactNode }) {
  const { signedIn, role, loading } = useAuth();
  if (loading) return <Booting />;
  if (signedIn && role) return <Navigate to={`/${role}`} replace />;
  return <>{children}</>;
}

const guarded = (role: Role, element: ReactNode) => (
  <RequireAuth role={role}>{element}</RequireAuth>
);

export const router = createBrowserRouter([
  { path: '/', element: <PublicOnly><Landing /></PublicOnly> },
  { path: '/login', element: <PublicOnly><Login /></PublicOnly> },
  { path: '/signup', element: <PublicOnly><Signup /></PublicOnly> },

  {
    element: <RequireAuth><AppShell /></RequireAuth>,
    children: [
      { path: '/profile', element: <Profile /> },
      { path: '/notifications', element: <Notifications /> },

      { path: '/farmer', element: guarded('farmer', <FarmerHome />) },
      { path: '/farmer/listings', element: guarded('farmer', <FarmerListings />) },
      { path: '/farmer/listings/new', element: guarded('farmer', <FarmerListingNew />) },
      { path: '/farmer/listings/:id', element: guarded('farmer', <FarmerListingDetail />) },
      { path: '/farmer/buyers', element: guarded('farmer', <FarmerBuyers />) },
      // Legacy alias: /farmer/requests rendered the same view as /farmer/buyers.
      { path: '/farmer/requests', element: guarded('farmer', <FarmerBuyers />) },
      { path: '/farmer/decisions', element: guarded('farmer', <FarmerDecisions />) },
      { path: '/farmer/orders', element: guarded('farmer', <FarmerOrders />) },
      // Same detail page as the buyer's: it reads the viewer's role and the
      // order's own logistics_arranged_by to decide what to offer, so both
      // sides get one screen instead of two that drift apart.
      { path: '/farmer/orders/:id', element: guarded('farmer', <BuyerOrderTrack />) },
      { path: '/farmer/transport', element: guarded('farmer', <FarmerTransport />) },

      { path: '/buyer', element: guarded('buyer', <BuyerHome />) },
      { path: '/buyer/market', element: guarded('buyer', <BuyerMarket />) },
      { path: '/buyer/product/:id', element: guarded('buyer', <BuyerProduct />) },
      { path: '/buyer/requests', element: guarded('buyer', <BuyerRequests />) },
      { path: '/buyer/requests/new', element: guarded('buyer', <BuyerRequestNew />) },
      { path: '/buyer/orders', element: guarded('buyer', <BuyerOrders />) },
      { path: '/buyer/orders/:id', element: guarded('buyer', <BuyerOrderTrack />) },

      { path: '/transporter', element: guarded('transporter', <TransporterHome />) },
      { path: '/transporter/jobs', element: guarded('transporter', <TransporterJobs />) },
      { path: '/transporter/jobs/:id', element: guarded('transporter', <TransporterJobDetail />) },
      { path: '/transporter/capacity', element: guarded('transporter', <TransporterCapacity />) },
      { path: '/transporter/capacity/new', element: guarded('transporter', <TransporterCapacityNew />) },
      { path: '/transporter/routes', element: guarded('transporter', <TransporterRoutes />) },
      { path: '/transporter/deliveries/:id', element: guarded('transporter', <TransporterDeliveries />) },
      { path: '/transporter/earnings', element: guarded('transporter', <TransporterEarnings />) },
    ],
  },

  { path: '*', element: <NotFound /> },
]);
