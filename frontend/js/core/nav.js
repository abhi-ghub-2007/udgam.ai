/* ===========================================================================
   nav.js - role-scoped bottom navigation.
   Max 5 items per role (nav-hierarchy / bottom-nav-limit). Every item pairs
   an icon with a visible text label - DESIGN.md forbids standalone icons.
   =========================================================================== */

import { store } from './store.js';
import { t } from './i18n.js';

const ICONS = {
  home:      'M12 3 2 12h3v8h6v-6h2v6h6v-8h3Z',
  listings:  'M4 4h7v7H4Zm9 0h7v7h-7ZM4 13h7v7H4Zm9 0h7v7h-7Z',
  market:    'M5 4h14l1 5a3 3 0 0 1-6 0 3 3 0 0 1-6 0 3 3 0 0 1-6 0Zm1 8h12v8H6Z',
  orders:    'M6 2h9l5 5v15H6Zm8 1v5h5M9 12h6M9 16h6',
  requests:  'M4 5h16v10H7l-3 3Z',
  transport: 'M3 7h11v8H3Zm11 3h4l3 3v2h-7Zm-7 8a2 2 0 1 0 0-4 2 2 0 0 0 0 4Zm11 0a2 2 0 1 0 0-4 2 2 0 0 0 0 4Z',
  jobs:      'M9 4h6v3h4v13H5V7h4Zm2 0v3h2V4Z',
  routes:    'M6 4a2 2 0 1 1 0 4 2 2 0 0 1 0-4Zm12 12a2 2 0 1 1 0 4 2 2 0 0 1 0-4ZM6 8v5a3 3 0 0 0 3 3h6a3 3 0 0 1 3 3',
  earnings:  'M12 2a10 10 0 1 0 0 20 10 10 0 0 0 0-20Zm1 15h-2v-1.5a3 3 0 0 1-2-2.5h2a1 1 0 0 0 2 0c0-1.8-4-1-4-4a3 3 0 0 1 2-2.6V5h2v1.4a3 3 0 0 1 2 2.6h-2a1 1 0 0 0-2 0c0 1.6 4 .9 4 4a3 3 0 0 1-2 2.5Z',
  profile:   'M12 12a4 4 0 1 0 0-8 4 4 0 0 0 0 8Zm0 2c-4 0-8 2-8 5v1h16v-1c0-3-4-5-8-5Z',
  logout:    'M10 3H5a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h5v-2H5V5h5Zm6.5 4L15 8.5 17.5 11H9v2h8.5L15 15.5 16.5 17 21 12.5Z',
};

// Each role gets exactly the five things it does most. `rail: true` marks an
// item that only fits the desktop side rail, where there is no five-slot cap.
const NAV = {
  farmer: [
    { path: '/farmer',           icon: 'home',      key: 'nav.home' },
    { path: '/farmer/listings',  icon: 'listings',  key: 'nav.my_listings' },
    { path: '/farmer/buyers',    icon: 'market',    key: 'nav.matching_buyers' },
    { path: '/farmer/orders',    icon: 'orders',    key: 'nav.orders', rail: true },
    { path: '/farmer/transport', icon: 'transport', key: 'nav.transport' },
    { path: '/notifications',    icon: 'requests',  key: 'nav.notifications', rail: true },
    { path: '/profile',          icon: 'profile',   key: 'nav.profile' },
  ],
  buyer: [
    { path: '/buyer',           icon: 'home',     key: 'nav.home' },
    { path: '/buyer/market',    icon: 'market',   key: 'nav.market' },
    { path: '/buyer/requests',  icon: 'requests', key: 'nav.my_requests' },
    { path: '/buyer/orders',    icon: 'orders',   key: 'nav.orders' },
    { path: '/profile',         icon: 'profile',  key: 'nav.profile' },
  ],
  transporter: [
    { path: '/transporter',          icon: 'home',     key: 'nav.home' },
    { path: '/transporter/jobs',     icon: 'jobs',     key: 'nav.jobs' },
    { path: '/transporter/capacity', icon: 'routes',   key: 'nav.my_routes' },
    { path: '/transporter/earnings', icon: 'earnings', key: 'nav.earnings' },
    { path: '/profile',              icon: 'profile',  key: 'nav.profile' },
  ],
};

function isActive(path, hash) {
  const current = (hash || '#/').slice(1);
  if (path === `/${store.get('profile')?.role}`) return current === path;
  return current === path || current.startsWith(`${path}/`);
}

const icon = (name, size = 24) => `
  <svg viewBox="0 0 24 24" width="${size}" height="${size}" aria-hidden="true" focusable="false">
    <path fill="currentColor" d="${ICONS[name]}"/>
  </svg>`;

export function renderNav() {
  const el = document.getElementById('bottom-nav');
  const rail = document.getElementById('side-rail');
  const role = store.get('profile')?.role;

  if (!role || !NAV[role]) {
    if (el) el.hidden = true;
    if (rail) rail.hidden = true;
    document.body.classList.remove('has-rail');
    return;
  }
  const items = NAV[role];

  // Bottom nav: mobile, hard cap of five (bottom-nav-limit).
  if (el) {
    el.hidden = false;
    el.innerHTML = items.filter((i) => !i.rail).slice(0, 5).map((item) => `
    <a class="bottom-nav__item" href="#${item.path}"
       ${isActive(item.path, location.hash) ? 'aria-current="page"' : ''}>
      ${icon(item.icon)}
      <span>${t(item.key)}</span>
    </a>`).join('');
  }

  // Side rail: desktop, every item including the rail-only ones.
  if (rail) {
    rail.hidden = false;
    document.body.classList.add('has-rail');
    rail.innerHTML = `
      <a class="side-rail__brand" href="#/${role}">
        <img src="./assets/logo.svg" alt="">
        <span>
          <span class="side-rail__name">UDGAM.ai</span><br>
          <span class="side-rail__tag">${t('landing.tagline')}</span>
        </span>
      </a>
      <nav class="side-rail__nav" aria-label="${t('nav.primary')}">
        ${items.map((item) => `
          <a class="side-rail__item" href="#${item.path}"
             ${isActive(item.path, location.hash) ? 'aria-current="page"' : ''}>
            ${icon(item.icon, 22)}<span>${t(item.key)}</span>
          </a>`).join('')}
      </nav>
      <div class="side-rail__foot">
        <button class="side-rail__item" type="button" data-action="sign-out"
                style="width:100%;background:none;border:0;cursor:pointer;text-align:left">
          ${icon('logout', 22)}<span>${t('auth.sign_out')}</span>
        </button>
      </div>`;
  }
}

export function mountNav() {
  // Delegated, registered once. Views never re-bind nav listeners.
  window.addEventListener('hashchange', renderNav);
}
