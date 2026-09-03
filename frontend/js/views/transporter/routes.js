/* AI-6 Route Optimization */

import { api } from '../../core/api.js';
import { t } from '../../core/i18n.js';

export const title = 'Optimize Route';

let route = null;

export async function render() {
  try {
    route = await api.get('/api/transport/optimize');
  } catch (err) {
    return `<div class="state state--error"><p class="state__body">${t('common.error_body')}</p></div>`;
  }

  if (!route.stops || route.stops.length === 0) {
    return `<div class="state state--empty"><p class="state__body">You don't have any active deliveries to optimize.</p></div>`;
  }

  return `
  <div class="stack stack--lg">
    <h1>Optimized Route</h1>

    <section class="card insight">
      <div class="row row--between">
        <h2>AI-6 Route Optimization</h2>
        <span class="badge">${t(`ai.method_${route.method}`)}</span>
      </div>
      <p style="margin-top:4px">Your deliveries have been sorted to minimize driving distance using ${route.solver.replace(/_/g, ' ')}.</p>
      
      <dl class="meta" style="margin-top: 16px">
        <dt>Naive Distance</dt><dd>${route.naive_distance_km} km</dd>
        <dt>Optimized Distance</dt><dd>${route.optimized_distance_km} km</dd>
        <dt>Distance Saved</dt><dd style="color:var(--c-primary); font-weight:bold">${route.distance_saved_pct}%</dd>
      </dl>
    </section>

    <section class="card">
      <h2>Route Plan</h2>
      <ul class="reasons" style="list-style: none; padding-left: 0; margin-top: 16px">
        ${route.stops.map((stop, i) => `
          <li style="margin-bottom: 12px; padding-left: 16px; border-left: 2px solid var(--c-primary)">
            <strong>Stop ${i + 1}: ${stop.label}</strong> 
            <span class="badge">${stop.type.toUpperCase()}</span><br>
            <span style="font-size: var(--fs-label); color: var(--c-ink-muted)">${stop.district}</span>
          </li>
        `).join('')}
      </ul>
    </section>
  </div>`;
}
