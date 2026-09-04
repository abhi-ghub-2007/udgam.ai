/* F-11 Farmer transport. Backed by GET /api/shipments, which RLS scopes to
   shipments on orders the caller participates in.

   Replaces the `upcoming` placeholder. Transport on this platform is arranged
   per order, so with no orders there is nothing to show — the empty state says
   that plainly and points at the step that actually comes first, rather than
   implying the farmer has missed something. */

import { api } from '../../core/api.js';
import { t, date, number } from '../../core/i18n.js';

export const title = 'market.transport_title';

const TONE = {
  delivered: 'success',
  in_transit: 'info', picked_up: 'info', assigned: 'info',
  cancelled: 'error',
  created: 'warning',
};

// The shipment's journey, in the order it happens. Drives the progress trail.
const JOURNEY = ['created', 'assigned', 'picked_up', 'in_transit', 'delivered'];

let shipments = [];
let loadError = null;

export async function render() {
  try {
    const res = await api.get('/api/shipments');
    shipments = res.shipments || [];
    loadError = null;
  } catch (err) {
    shipments = [];
    loadError = err;
  }

  if (loadError) {
    return `<div class="stack stack--lg">
      <h1>${t('market.transport_title')}</h1>
      <div class="state state--error" role="alert">
        <p class="state__body">${loadError.message || t('common.error_body')}</p>
        <button class="btn btn--primary" data-action="retry-transport">${t('common.retry')}</button>
      </div>
    </div>`;
  }

  return `<div class="stack stack--lg">
    <h1>${t('market.transport_title')}</h1>
    <p class="state__body">${t('market.transport_intro')}</p>
    <section class="grid">
      ${shipments.length
        ? shipments.map(card).join('')
        : `<div class="state state--empty">
             <h2 class="state__title">${t('market.transport_none_title')}</h2>
             <p class="state__body">${t('market.transport_empty')}</p>
             <a class="btn btn--primary" href="#/farmer/orders">${t('market.orders_title')}</a>
           </div>`}
    </section>
  </div>`;
}

function trail(status) {
  const at = JOURNEY.indexOf(status);
  if (status === 'cancelled' || at < 0) return '';
  return `<div class="row row--wrap" style="gap:var(--sp-xs)">
    ${JOURNEY.map((step, i) => `
      <span class="badge badge--${i <= at ? 'success' : 'info'}"
            style="${i <= at ? '' : 'opacity:.45'}">
        ${t(`market.shipment_step.${step}`)}
      </span>`).join('')}
  </div>`;
}

/** Real distance once travelled, planned distance before that. The schema has
    both; there is no generic `distance_km`. */
function dist(s) {
  const v = s.actual_distance_km ?? s.planned_distance_km;
  return v == null ? null : Number(v);
}

function card(s) {
  const status = (s.status || 'created').toLowerCase();
  return `
  <article class="card stack stack--sm">
    <div class="row row--between">
      <h3 class="card__title" style="margin:0">${s.order_no || t('market.shipment')}</h3>
      <span class="badge badge--${TONE[status] || 'info'}">
        ${t(`market.shipment_step.${status}`)}
      </span>
    </div>

    ${trail(status)}

    ${dist(s) != null || s.eta_at ? `
      <div class="row row--between row--wrap">
        ${dist(s) != null
          ? `<span class="card__meta">${t('market.distance_label')}: ${number(Math.round(dist(s)))} km</span>` : ''}
        ${s.eta_at && status !== 'delivered'
          ? `<span class="card__meta">${t('market.eta')}: ${date(s.eta_at)}</span>` : ''}
      </div>` : ''}

    ${s.picked_up_at || s.delivered_at ? `
      <div class="row row--between row--wrap">
        ${s.picked_up_at ? `<span class="card__meta">${t('market.picked_up_on')}: ${date(s.picked_up_at)}</span>` : ''}
        ${s.delivered_at ? `<span class="card__meta">${t('market.delivered_on')}: ${date(s.delivered_at)}</span>` : ''}
      </div>` : ''}
  </article>`;
}

export function mount(root) {
  const onClick = (e) => {
    if (e.target.closest('[data-action="retry-transport"]')) location.reload();
  };
  root.addEventListener('click', onClick);
  return () => root.removeEventListener('click', onClick);
}
