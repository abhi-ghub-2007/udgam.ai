/* B-1 buyer dashboard. Backed by GET /api/dashboard/buyer. */

import { store } from '../../core/store.js';
import { t, money } from '../../core/i18n.js';
import { loadDashboard, statCard, section, emptyState } from '../dashboard-common.js';

export const title = 'buyer.dashboard.title';

export async function render() {
  const profile = store.get('profile') || {};
  let d = {};
  try {
    ({ data: d } = await loadDashboard('/api/dashboard/buyer', 'dash.buyer'));
  } catch { d = {}; }

  const isBulk = store.get('details')?.buyer_type === 'bulk';

  return `
  <div class="stack stack--lg">
    <h1>${t('farmer.dashboard.greeting', { name: profile.full_name || '' })}</h1>

    <section class="grid">
      ${statCard('buyer.dashboard.active_orders', d.active_orders ?? 0)}
      ${statCard('buyer.dashboard.my_requests',   d.open_requests ?? 0)}
      ${statCard('buyer.dashboard.saved_farmers', d.saved_farmers ?? 0)}
    </section>

    ${section('buyer.dashboard.recommended',
      d.recommended?.length
        ? `<div class="grid">${d.recommended.map(card).join('')}</div>`
        : emptyState('common.none_yet', '#/buyer/market', 'nav.market'))}

    ${isBulk ? section('buyer.dashboard.my_requests',
      d.requests?.length
        ? `<div class="stack stack--sm">${d.requests.map(reqCard).join('')}</div>`
        : emptyState('common.none_yet', '#/buyer/requests/new', 'nav.my_requests')) : ''}
  </div>`;
}

function card(p) {
  const grade = (p.grade || 'c').toLowerCase();
  return `<a class="card card--interactive" href="#/buyer/product/${p.id}">
    <div class="row row--between">
      <span class="card__title">${p.crop_name}</span>
      ${p.grade ? `<span class="badge badge--grade-${grade}">${t(`product.grade_${grade}`)}</span>` : ''}
    </div>
    <div class="card__meta">${p.quantity_kg} ${t('common.kg')} · ${money(p.asking_price_paise)} ${t('common.per_kg')}</div>
    <div class="card__meta">${p.district ?? ''}</div>
  </a>`;
}

function reqCard(r) {
  // A requirement carries a request_status ('open', 'fulfilled', ...), not an
  // order_status, so it must not be looked up in order.status.* — that printed
  // a raw "order.status.OPEN" on the dashboard. The link goes to the requests
  // list because #/buyer/requests/:id is not a registered route.
  const status = String(r.status || 'open').toLowerCase();
  return `<a class="card card--interactive" href="#/buyer/requests">
    <div class="card__title">${r.crop_name} · ${r.quantity_kg} ${t('common.kg')}</div>
    <div class="card__meta">${t(`market.request_status.${status}`)}</div>
  </a>`;
}
