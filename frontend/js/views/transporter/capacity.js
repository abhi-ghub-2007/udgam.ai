/* T-5 My Routes & Empty Legs */

import { api } from '../../core/api.js';
import { t, number } from '../../core/i18n.js';

export const title = 'My Routes';

let capacity = [];

export async function render() {
  try {
    const res = await api.get('/api/transport/capacity/mine');
    capacity = res.capacity || [];
  } catch (err) {
    return `<div class="state state--error"><p class="state__body">${t('common.error_body')}</p></div>`;
  }

  return `
  <div class="stack stack--lg">
    <div class="row row--between">
      <h1>My Routes</h1>
      <a class="btn btn--primary" href="#/transporter/capacity/new">Post Empty Leg</a>
    </div>

    <section class="card insight" style="margin-bottom: 16px;">
      <div class="row row--between">
        <h2>Smart Route Optimization</h2>
        <span class="badge">AI-6</span>
      </div>
      <p style="margin-top:4px">Optimize your current deliveries for the fastest route.</p>
      <a class="btn btn--secondary" href="#/transporter/routes" style="margin-top:12px; display:inline-block">Optimize Route</a>
    </section>

    <section class="grid">
      ${capacity.length 
        ? capacity.map(capCard).join('')
        : `<div class="state state--empty"><p class="state__body">You haven't posted any routes or empty legs.</p></div>`
      }
    </section>
  </div>`;
}

function capCard(c) {
  return `
  <article class="card">
    <div class="row row--between">
      <h3 style="margin:0">${c.capacity_type.replace('_', ' ').toUpperCase()}</h3>
      <span class="badge" style="background:var(--c-surface);border:1px solid var(--c-ink-muted)">
        ${c.status.toUpperCase()}
      </span>
    </div>
    <div class="card__meta" style="margin-top:8px">
      ${c.origin_district || 'Any'} → ${c.dest_district || 'Any'}
    </div>
    <div class="card__meta">
      Available: ${number(c.available_capacity_kg)} / ${number(c.total_capacity_kg)} ${t('common.kg')}
    </div>
  </article>`;
}
