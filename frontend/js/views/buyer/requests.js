/* B-6 My Requirements.

   The cards used to be clickable and navigated to #/buyer/requests/:id, which
   is not a registered route — every click landed on "Page not found". There is
   no per-request detail screen yet, so the card is presented as information
   rather than wearing an affordance it cannot honour. */

import { api } from '../../core/api.js';
import { t, money, number } from '../../core/i18n.js';
import { store } from '../../core/store.js';

export const title = 'nav.my_requests';

let requests = [];

export async function render() {
  const profile = store.get('profile') || {};

  try {
    const res = await api.get('/api/buyer-requests/mine');
    requests = res.requests || [];
  } catch (err) {
    return `<div class="state state--error"><p class="state__body">${t('common.error_body')}</p></div>`;
  }

  return `
  <div class="stack stack--lg">
    <div class="row row--between">
      <h1>${t('nav.my_requests')}</h1>
      <a class="btn btn--primary" href="#/buyer/requests/new">Post Requirement</a>
    </div>

    <section class="grid">
      ${requests.length 
        ? requests.map(reqCard).join('')
        : `<div class="state state--empty"><p class="state__body">You haven't posted any requirements yet.</p></div>`
      }
    </section>
  </div>`;
}

function reqCard(r) {
  return `
  <article class="card">
    <div class="row row--between">
      <h3 style="margin:0">${r.crop_name || 'Produce'}</h3>
      <span class="badge" style="background:var(--c-surface);border:1px solid var(--c-ink-muted)">
        ${r.status.toUpperCase()}
      </span>
    </div>
    <div class="card__meta" style="margin-top:8px">
      ${number(r.quantity_kg)} ${t('common.kg')}
    </div>
    <div class="card__meta">
      ${r.target_price_paise ? `Target: ${money(r.target_price_paise)} / kg` : 'No target price'}
    </div>
    <div class="card__meta" style="margin-top:8px; color:var(--c-primary); font-weight:bold;">
      ${r.match_count || 0} Matches Found
    </div>
  </article>`;
}
