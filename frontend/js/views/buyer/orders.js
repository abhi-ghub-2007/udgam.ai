/* B-4 My Orders */

import { api } from '../../core/api.js';
import { t, money, date } from '../../core/i18n.js';

export const title = 'market.orders_title';

let orders = [];

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
    
    <div class="tabs" style="margin-bottom: 16px;">
      <button class="btn btn--outline" disabled>All</button>
      <button class="btn btn--ghost">Pending</button>
      <button class="btn btn--ghost">In Transit</button>
      <button class="btn btn--ghost">Delivered</button>
    </div>

    <section class="grid">
      ${orders.length 
        ? orders.map(orderCard).join('')
        : `<div class="state state--empty"><p class="state__body">${t('market.orders_empty')}</p></div>`
      }
    </section>
  </div>`;
}

function orderCard(o) {
  const item = o.items?.[0] || {};
  return `
  <article class="card card--interactive" onclick="location.hash='#/buyer/orders/${o.id}'" style="cursor:pointer">
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
