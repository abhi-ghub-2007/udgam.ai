/* Shared dashboard scaffolding for the three role homes.

   C-5: renders the cached payload immediately when offline and raises the
   stale banner, instead of showing a blank screen or a spinner that never
   resolves.
*/

import { api } from '../core/api.js';
import { store, cache } from '../core/store.js';
import { t, money, number } from '../core/i18n.js';

export function statCard(labelKey, value) {
  return `<div class="card stat">
    <span class="stat__value">${value}</span>
    <span class="stat__label">${t(labelKey)}</span>
  </div>`;
}

export function emptyState(messageKey, actionHref, actionKey) {
  return `<div class="state state--empty">
    <p class="state__body">${t(messageKey)}</p>
    ${actionHref ? `<a class="btn btn--primary" href="${actionHref}">${t(actionKey)}</a>` : ''}
  </div>`;
}

export function section(titleKey, bodyHtml) {
  return `<section class="stack stack--sm">
    <h2>${t(titleKey)}</h2>
    ${bodyHtml}
  </section>`;
}

/** Fetch a dashboard payload, falling back to the cached copy when offline. */
export async function loadDashboard(path, cacheKey) {
  try {
    const data = await api.get(path);
    cache.save(cacheKey, data);
    store.set('stale', false);
    return { data, stale: false };
  } catch (err) {
    const cached = cache.load(cacheKey);
    if (cached) {
      store.set('stale', true);
      return { data: cached.payload, stale: true, cachedAt: cached.at };
    }
    throw err;
  }
}

export const fmt = { money, number, t };
