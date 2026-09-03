/* ===========================================================================
   routes.js - the route table. One place to see every screen and who may
   reach it. Later phases add rows here rather than inventing their own
   navigation.
   =========================================================================== */

import { route } from './core/router.js';

import * as landing from './views/landing.js?v=2';
import * as login from './views/login.js?v=2';
import * as signup from './views/signup.js?v=2';
import * as profile from './views/profile.js';
import * as farmerHome from './views/farmer/home.js';
import * as farmerListings from './views/farmer/listings.js';
import * as farmerListingNew from './views/farmer/listing-new.js';
import * as farmerListingDetail from './views/farmer/listing-detail.js';
import * as farmerBuyers from './views/farmer/buyers.js';
import { make as upcoming } from './views/farmer/upcoming.js';
import * as buyerHome from './views/buyer/home.js';
import * as buyerMarket from './views/buyer/market.js';
import * as buyerProduct from './views/buyer/product.js';
import * as buyerRequests from './views/buyer/requests.js';
import * as buyerRequestNew from './views/buyer/request-new.js';
import * as buyerOrders from './views/buyer/orders.js';
import * as buyerOrderTrack from './views/buyer/order-track.js';

import * as transporterHome from './views/transporter/home.js';
import * as transporterJobs from './views/transporter/jobs.js';
import * as transporterJobDetail from './views/transporter/job-detail.js';
import * as transporterCapacity from './views/transporter/capacity.js';
import * as transporterCapacityNew from './views/transporter/capacity-new.js';
import * as transporterRoutes from './views/transporter/routes.js';
import * as transporterDeliveries from './views/transporter/deliveries.js';
import * as transporterEarnings from './views/transporter/earnings.js';

const FARMER = { roles: ['farmer'] };

export function registerRoutes() {
  route('/', landing, { public: true });
  route('/login', login, { public: true });
  route('/signup', signup, { public: true });

  route('/profile', profile);
  route('/notifications', upcoming('notifications'));

  // --- farmer ------------------------------------------------------------
  route('/farmer', farmerHome, FARMER);
  route('/farmer/listings', farmerListings, FARMER);
  // `new` is registered BEFORE `:id` so it is not swallowed by the wildcard.
  route('/farmer/listings/new', farmerListingNew, FARMER);
  route('/farmer/listings/:id', farmerListingDetail, FARMER);
  route('/farmer/buyers', farmerBuyers, FARMER);
  route('/farmer/requests', farmerBuyers, FARMER);
  route('/farmer/orders', upcoming('orders'), FARMER);
  route('/farmer/transport', upcoming('transport'), FARMER);

  const BUYER = { roles: ['buyer'] };
  route('/buyer', buyerHome, BUYER);
  route('/buyer/market', buyerMarket, BUYER);
  route('/buyer/product/:id', buyerProduct, BUYER);
  route('/buyer/requests', buyerRequests, BUYER);
  route('/buyer/requests/new', buyerRequestNew, BUYER);
  route('/buyer/orders', buyerOrders, BUYER);
  route('/buyer/orders/:id', buyerOrderTrack, BUYER);

  const TRANSPORTER = { roles: ['transporter'] };
  route('/transporter', transporterHome, TRANSPORTER);
  route('/transporter/jobs', transporterJobs, TRANSPORTER);
  route('/transporter/jobs/:id', transporterJobDetail, TRANSPORTER);
  route('/transporter/capacity', transporterCapacity, TRANSPORTER);
  route('/transporter/capacity/new', transporterCapacityNew, TRANSPORTER);
  route('/transporter/routes', transporterRoutes, TRANSPORTER);
  route('/transporter/deliveries/:id', transporterDeliveries, TRANSPORTER);
  route('/transporter/earnings', transporterEarnings, TRANSPORTER);
}
