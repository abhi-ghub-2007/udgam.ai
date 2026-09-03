/* F-1 farmer dashboard. Backed by GET /api/dashboard/farmer plus the AI-5
   matching feed, laid out in the Stitch hero + tiles + bento arrangement.

   Every number on this screen comes from the API. Where a Phase 3 model is not
   built yet (price prediction, demand forecast), the panel says what it is
   based on rather than showing an invented figure. */

import { store } from '../../core/store.js';
import { t, money, number } from '../../core/i18n.js';
import { api } from '../../core/api.js';
import { loadDashboard } from '../dashboard-common.js';
import { produceCard } from './cards.js';

export const title = 'farmer.dashboard.title';

let payload = null;
let best = null;

export async function render() {
  const profile = store.get('profile') || {};

  try {
    ({ data: payload } = await loadDashboard('/api/dashboard/farmer', 'dash.farmer'));
  } catch {
    payload = null;
  }

  // Top-ranked open request across this farmer's crops — the "selling
  // opportunity". Real AI-5 output, not a placeholder.
  try {
    const { matches } = await api.get('/api/matching/buyers');
    best = matches?.[0] || null;
  } catch {
    best = null;
  }

  const d = payload || {};
  const listings = d.listings || [];
  const totalKg = listings.reduce((s, p) => s + (p.available_quantity_kg || 0), 0);
  // Expected earnings = what the live listings are worth at asking price.
  const expected = listings.reduce(
    (s, p) => s + (p.available_quantity_kg || 0) * (p.asking_price_paise || 0), 0);

  return `
  <div class="stack stack--lg">
    <section class="hero">
      <span class="hero__eyebrow">${t('auth.welcome_back')}</span>
      <h1 class="hero__title">${t('farmer.dashboard.greeting', { name: profile.full_name || '' })}</h1>
      <p class="hero__body">${t('farmer.dashboard.subtitle')}</p>
      <div class="row" style="gap:var(--sp-sm)">
        <a class="btn btn--primary" href="#/farmer/listings/new">${t('market.list_new')}</a>
        <a class="btn btn--outline" href="#/farmer/buyers">${t('market.matching_title')}</a>
      </div>
    </section>

    <section class="grid grid--3">
      ${tile('inventory', 'farmer.dashboard.active_listings',
             `${d.active_listings ?? 0}`, `${number(totalKg)} ${t('common.kg')}`)}
      ${tile('gold', 'farmer.dashboard.earnings_expected',
             money(expected, { compact: true }), t('market.at_asking_price'))}
      ${tile('green', 'farmer.dashboard.open_requests_count',
             `${(d.open_requests || []).length}`, t('market.for_your_crops'))}
      ${tile('inventory', 'farmer.dashboard.active_orders',
             `${d.active_orders ?? 0}`, t('market.orders_phase_note'))}
    </section>

    ${best ? sellingOpportunity(best) : ''}

    <section class="grid">
      <div class="card--ambient" style="padding:var(--sp-lg)">
        <h2 style="margin-top:0">${t('market.quick_actions')}</h2>
        <div class="quick-grid">
          <a class="quick" href="#/farmer/listings/new">
            <span class="quick__icon">${plus}</span>${t('market.list_new')}
          </a>
          <a class="quick" href="#/farmer/decisions">
            <span class="quick__icon">${rupee}</span>${t('decide.title')}
          </a>
          <a class="quick" href="#/farmer/buyers">
            <span class="quick__icon">${search}</span>${t('market.find_buyers')}
          </a>
          <a class="quick" href="#/farmer/listings">
            <span class="quick__icon">${box}</span>${t('market.my_listings_title')}
          </a>
          <a class="quick" href="#/profile">
            <span class="quick__icon">${person}</span>${t('nav.profile')}
          </a>
        </div>
      </div>
    </section>

    <section class="stack stack--sm">
      <div class="section-head">
        <h2>${t('farmer.dashboard.active_listings')}</h2>
        <a href="#/farmer/listings">${t('market.view_all')} →</a>
      </div>
      ${listings.length
        ? `<div class="grid">${listings.map(produceCard).join('')}</div>`
        : `<div class="state state--empty">
             <p class="state__body">${t('market.empty_listings')}</p>
             <a class="btn btn--primary" href="#/farmer/listings/new">${t('market.list_new')}</a>
           </div>`}
    </section>
  </div>`;
}

function tile(variant, labelKey, value, note) {
  const cls = variant === 'gold' ? 'tile__icon tile__icon--gold'
            : variant === 'green' ? 'tile__icon tile__icon--green' : 'tile__icon';
  const glyph = variant === 'gold' ? rupee : variant === 'green' ? chat : box;
  return `
  <div class="tile">
    <div class="tile__top">
      <span class="${cls}">${glyph}</span>
      <span class="tile__note">${note}</span>
    </div>
    <div>
      <p class="tile__label">${t(labelKey)}</p>
      <p class="tile__value">${value}</p>
    </div>
  </div>`;
}

/** The single best open request right now, with the backend's own reasons. */
function sellingOpportunity(m) {
  const total = m.target_price_paise
    ? money(Math.round(m.quantity_kg * m.target_price_paise)) : null;
  return `
  <section class="insight">
    <span class="insight__eyebrow">${t('market.selling_opportunity')}</span>
    <h2 class="insight__title">
      ${m.crop_name} · ${number(m.quantity_kg)} ${t('common.kg')}
      ${m.delivery_district ? `→ ${m.delivery_district}` : ''}
    </h2>
    <p class="insight__body">
      ${m.target_price_paise
        ? t('market.buyer_offers', {
            price: `${money(m.target_price_paise)} ${t('common.per_kg')}`,
            total: total,
          })
        : t('market.buyer_no_target')}
    </p>
    <ul class="reasons">${(m.reasons || []).map((r) => `<li>${r}</li>`).join('')}</ul>
    <div class="row" style="gap:var(--sp-sm)">
      <a class="btn btn--primary" href="#/farmer/buyers">${t('market.review_offer')}</a>
      <span class="badge">${t('ai.method_ALGORITHMIC')}</span>
    </div>
  </section>`;
}

const svg = (d, size = 24) =>
  `<svg viewBox="0 0 24 24" width="${size}" height="${size}" aria-hidden="true"><path fill="currentColor" d="${d}"/></svg>`;
const box    = svg('M4 4h7v7H4Zm9 0h7v7h-7ZM4 13h7v7H4Zm9 0h7v7h-7Z');
const rupee  = svg('M6 3h12v2h-4.2c.7.5 1.2 1.2 1.4 2H18v2h-2.8c-.4 2.3-2.3 4-4.7 4H9.9l6.4 6H13l-6.5-6.2V15H9c1.9 0 3.4-1.1 3.8-3H6V10h6.8c-.4-1.2-1.5-2-3-2H6Z');
const chat   = svg('M4 5h16v10H7l-3 3Z');
const plus   = svg('M11 5h2v6h6v2h-6v6h-2v-6H5v-2h6Z');
const search = svg('M10 4a6 6 0 1 1 0 12 6 6 0 0 1 0-12Zm0 2a4 4 0 1 0 0 8 4 4 0 0 0 0-8Zm5.7 8.3 4 4-1.4 1.4-4-4Z');
const person = svg('M12 12a4 4 0 1 0 0-8 4 4 0 0 0 0 8Zm0 2c-4 0-8 2-8 5v1h16v-1c0-3-4-5-8-5Z');
