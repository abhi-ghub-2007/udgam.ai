/* T-7 Earnings History */

import { api } from '../../core/api.js';
import { t, money, date } from '../../core/i18n.js';
import { statCard } from '../dashboard-common.js';

export const title = 'Earnings';

let data = null;

export async function render() {
  try {
    data = await api.get('/api/transport/earnings');
  } catch (err) {
    return `<div class="state state--error"><p class="state__body">${t('common.error_body')}</p></div>`;
  }

  return `
  <div class="stack stack--lg">
    <h1>Earnings Summary</h1>
    
    <section class="grid">
      ${statCard('Total Earnings', money(data.total_earnings_paise ?? 0))}
      ${statCard('This Month', money(data.this_month_paise ?? 0))}
      ${statCard('Total Distance', `${data.total_distance_km ?? 0} km`)}
    </section>
    
    <div class="card insight" style="margin-top: 16px;">
      <h2 style="font-size: var(--fs-h3)">Average Earnings per km</h2>
      <p style="font-size: var(--fs-h1); color: var(--c-primary); font-weight: bold; margin-top: 8px;">
        ${money(data.avg_per_km_paise ?? 0)}
      </p>
    </div>

    <section class="card">
      <div class="section-head">
        <h2>History</h2>
        <span class="badge">${data.completed_deliveries} Completed</span>
      </div>
      <div class="stack stack--sm" style="margin-top: 16px">
        ${data.history?.length 
          ? data.history.map(itemCard).join('')
          : `<div class="state state--empty"><p class="state__body">No earnings history yet.</p></div>`
        }
      </div>
    </section>
  </div>`;
}

function itemCard(item) {
  return `
  <article class="card card--interactive">
    <div class="row row--between">
      <h3 style="margin:0">Order ${item.order_no}</h3>
      <span class="badge" style="background:var(--c-surface)">${item.status.toUpperCase()}</span>
    </div>
    <div class="card__meta" style="margin-top:8px">
      ${money(item.earnings_paise)} · ${item.distance_km} km
    </div>
    ${item.delivered_at ? `<div class="card__meta">Delivered on ${date(item.delivered_at)}</div>` : ''}
  </article>`;
}
