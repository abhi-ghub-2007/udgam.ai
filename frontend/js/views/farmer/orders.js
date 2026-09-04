/* F-10 Farmer orders. Backed by GET /api/orders, which returns every order the
   caller participates in — RLS and is_order_participant() scope it, so a farmer
   sees only their own.

   Replaces the `upcoming` placeholder. The filter tabs actually filter (the
   buyer equivalent had dead buttons), and every listener is delegated from the
   view root per router.js — no inline handlers. */

import { api } from '../../core/api.js';
import { t, money, date, number } from '../../core/i18n.js';

export const title = 'market.orders_title';

// Grouped so one tab covers the several underlying states a farmer thinks of
// as the same thing. 'all' is the default.
const FILTERS = {
  all: null,
  active: ['PLACED', 'ACCEPTED', 'PAYMENT_HELD', 'LOGISTICS_ASSIGNED',
           'PICKED_UP', 'IN_TRANSIT'],
  delivered: ['DELIVERED', 'CLOSED'],
  cancelled: ['CANCELLED', 'DISPUTED'],
};

const TONE = {
  CLOSED: 'success', DELIVERED: 'success',
  CANCELLED: 'error', DISPUTED: 'error',
  IN_TRANSIT: 'info', PICKED_UP: 'info', LOGISTICS_ASSIGNED: 'info',
};

let orders = [];
let loadError = null;
let active = 'all';

export async function render() {
  try {
    const res = await api.get('/api/orders');
    orders = res.orders || [];
    loadError = null;
  } catch (err) {
    orders = [];
    loadError = err;
  }

  if (loadError) {
    return `<div class="stack stack--lg">
      <h1>${t('market.orders_title')}</h1>
      <div class="state state--error" role="alert">
        <p class="state__body">${loadError.message || t('common.error_body')}</p>
        <button class="btn btn--primary" data-action="retry-orders">${t('common.retry')}</button>
      </div>
    </div>`;
  }

  return `<div class="stack stack--lg">
    <h1>${t('market.orders_title')}</h1>
    ${tabs()}
    <section id="order-list" class="grid">${list()}</section>
  </div>`;
}

function tabs() {
  const count = (key) => key === 'all'
    ? orders.length
    : orders.filter((o) => FILTERS[key].includes(o.status)).length;
  return `<div class="chip-row" role="tablist" aria-label="${t('market.orders_title')}">
    ${Object.keys(FILTERS).map((key) => `
      <button type="button" class="chip" data-filter="${key}" role="tab"
              aria-selected="${key === active}">
        ${t(`market.orders_filter.${key}`)} (${count(key)})
      </button>`).join('')}
  </div>`;
}

function visible() {
  const allowed = FILTERS[active];
  return allowed ? orders.filter((o) => allowed.includes(o.status)) : orders;
}

function list() {
  const rows = visible();
  if (!rows.length) {
    return `<div class="state state--empty">
      <p class="state__body">${orders.length
        ? t('market.orders_none_in_filter')
        : t('market.orders_empty')}</p>
      ${orders.length ? '' : `<a class="btn btn--primary" href="#/farmer/buyers">${t('market.matching_title')}</a>`}
    </div>`;
  }
  return rows.map(card).join('');
}

function card(o) {
  const item = o.items?.[0] || {};
  const extra = (o.items?.length || 0) - 1;
  const tone = TONE[o.status] || 'warning';
  return `
  <article class="card stack stack--sm">
    <div class="row row--between">
      <h3 class="card__title" style="margin:0">${o.order_no}</h3>
      <span class="badge badge--${tone}">${t(`order.status.${o.status}`)}</span>
    </div>

    <div class="card__meta">
      ${item.crop_name || t('market.produce')} ·
      ${number(item.quantity_kg || 0)} ${t('common.kg')}
      ${extra > 0 ? ` · ${t('market.plus_more_items', { n: extra })}` : ''}
    </div>

    <div class="row row--between row--wrap">
      <span class="card__meta">${t('market.buyer_label')}: ${o.counterparty?.full_name || '—'}</span>
      <span class="card__meta">${o.placed_at ? date(o.placed_at) : date(o.created_at)}</span>
    </div>

    <div class="row row--between">
      <span class="card__meta">${t('market.your_payout')}</span>
      <span class="tile__value" style="font-size:var(--fs-h3)">${money(o.farmer_payout_paise)}</span>
    </div>

    ${['CANCELLED', 'DISPUTED'].includes(o.status) ? `
      <a class="btn btn--outline btn--block" href="#/farmer/decisions"
         data-order="${o.id}">${t('market.find_new_exit')}</a>` : ''}
  </article>`;
}

export function mount(root) {
  const onClick = (e) => {
    const retry = e.target.closest('[data-action="retry-orders"]');
    if (retry) { location.reload(); return; }

    const tab = e.target.closest('[data-filter]');
    if (!tab) return;
    active = tab.dataset.filter;
    root.querySelectorAll('[data-filter]').forEach((b) =>
      b.setAttribute('aria-selected', String(b.dataset.filter === active)));
    const listEl = root.querySelector('#order-list');
    if (listEl) listEl.innerHTML = list();
  };

  root.addEventListener('click', onClick);
  return () => root.removeEventListener('click', onClick);
}
