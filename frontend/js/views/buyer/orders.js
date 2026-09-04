/* B-4 My Orders */

import { api } from '../../core/api.js';
import { t, money, date } from '../../core/i18n.js';

export const title = 'market.orders_title';

// Same grouping the farmer view uses, so both roles read the same words.
const FILTERS = {
  all: null,
  active: ['PLACED', 'ACCEPTED', 'PAYMENT_HELD', 'LOGISTICS_ASSIGNED',
           'PICKED_UP', 'IN_TRANSIT'],
  delivered: ['DELIVERED', 'CLOSED'],
  cancelled: ['CANCELLED', 'DISPUTED'],
};

let orders = [];
let active = 'all';

export async function render() {
  try {
    const res = await api.get('/api/orders');
    orders = res.orders || [];
  } catch (err) {
    return `<div class="state state--error"><p class="state__body">${t('common.error_body')}</p></div>`;
  }

  return `
  <div class="stack stack--lg">
    <h1>${t('market.orders_title')}</h1>
    
    ${tabs()}

    <section id="buyer-order-list" class="grid">${list()}</section>
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

function list() {
  const allowed = FILTERS[active];
  const rows = allowed ? orders.filter((o) => allowed.includes(o.status)) : orders;
  if (!rows.length) {
    return `<div class="state state--empty"><p class="state__body">${
      orders.length ? t('market.orders_none_in_filter') : t('market.orders_empty')
    }</p></div>`;
  }
  return rows.map(orderCard).join('');
}

export function mount(root) {
  const onClick = (e) => {
    const card = e.target.closest('[data-order-id]');
    if (card) { location.hash = `#/buyer/orders/${card.dataset.orderId}`; return; }
    const tab = e.target.closest('[data-filter]');
    if (!tab) return;
    active = tab.dataset.filter;
    root.querySelectorAll('[data-filter]').forEach((b) =>
      b.setAttribute('aria-selected', String(b.dataset.filter === active)));
    const el = root.querySelector('#buyer-order-list');
    if (el) el.innerHTML = list();
  };
  root.addEventListener('click', onClick);
  return () => root.removeEventListener('click', onClick);
}

function orderCard(o) {
  const item = o.items?.[0] || {};
  return `
  <article class="card card--interactive" data-order-id="${o.id}"
           role="link" tabindex="0" style="cursor:pointer">
    <div class="row row--between">
      <h3 style="margin:0">${o.order_no}</h3>
      <span class="badge" style="background:var(--c-surface);border:1px solid var(--c-ink-muted)">
        ${t(`order.status.${o.status}`)}
      </span>
    </div>
    <div class="card__meta" style="margin-top:8px">
      ${item.crop_name || 'Produce'} · ${item.quantity_kg || 0} ${t('common.kg')}
    </div>
    <div class="card__meta">
      Total: ${money(o.buyer_total_paise)} · Placed: ${date(o.placed_at)}
    </div>
    <div class="card__meta">
      Farmer: ${o.counterparty?.full_name || '—'}
    </div>
  </article>`;
}
