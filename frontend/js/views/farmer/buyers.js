/* F-5 / F-6 Matching Buyers.

   Two real feeds on one screen:
     GET /api/matching/buyers  — open requests ranked against MY listings (AI-5)
     GET /api/buyer-requests   — EVERY open request, matched or not (the F-6
                                 requirement: a farmer is never shown a
                                 filtered-down market)
   The score and its `reasons[]` come from the backend and are shown verbatim,
   labelled ALGORITHMIC. */

import { api } from '../../core/api.js';
import { t, money, number } from '../../core/i18n.js';

export const title = 'market.matching_title';

let ranked = [];
let all = [];
let note = null;

export async function render() {
  const [a, b] = await Promise.allSettled([
    api.get('/api/matching/buyers'),
    api.get('/api/buyer-requests'),
  ]);

  ranked = a.status === 'fulfilled' ? (a.value.matches || []) : [];
  note = a.status === 'fulfilled' ? a.value.note : null;
  all = b.status === 'fulfilled' ? (b.value.requests || []) : [];

  if (a.status === 'rejected' && b.status === 'rejected') {
    return `<div class="state state--error" role="alert">
      <h2 class="state__title">${t('common.error_title')}</h2>
      <p class="state__body">${t('common.error_body')}</p>
    </div>`;
  }

  const rankedIds = new Set(ranked.map((r) => r.id));
  const rest = all.filter((r) => !rankedIds.has(r.id));

  return `
  <div class="stack stack--lg">
    <h1>${t('market.matching_title')}</h1>

    <section class="stack stack--sm">
      <div class="section-head">
        <h2>${t('market.ranked_for_you')}</h2>
        <span class="badge">${t('ai.method_ALGORITHMIC')}</span>
      </div>
      ${ranked.length
        ? ranked.map((m) => requestCard(m, true)).join('')
        : `<div class="state state--empty">
             <p class="state__body">${note || t('market.no_matches')}</p>
             <a class="btn btn--primary" href="#/farmer/listings/new">${t('market.list_new')}</a>
           </div>`}
    </section>

    <section class="stack stack--sm">
      <div class="section-head"><h2>${t('market.all_open_requests')}</h2></div>
      ${rest.length
        ? rest.map((m) => requestCard(m, false)).join('')
        : `<div class="state state--empty">
             <p class="state__body">${t('market.empty_open_requests')}</p>
           </div>`}
    </section>
  </div>`;
}

function requestCard(m, scored) {
  return `
  <article class="card--ambient match">
    <div class="match__head">
      <div>
        <h3 style="margin:0">${m.crop_name || '—'} · ${number(m.quantity_kg)} ${t('common.kg')}</h3>
        <p style="margin:4px 0 0;color:var(--c-ink-muted)">
          ${m.delivery_district || '—'}
          ${m.needed_by ? ` · ${t('market.needed_by')} ${m.needed_by}` : ''}
        </p>
      </div>
      ${scored ? `<div class="match__score">
        <b>${Math.round(m.score)}</b><span>${t('market.match_score')}</span>
      </div>` : ''}
    </div>

    <dl class="meta">
      <dt>${t('market.min_grade')}</dt><dd>${m.min_grade || '—'}</dd>
      <dt>${t('market.target_price')}</dt>
      <dd>${m.target_price_paise ? `${money(m.target_price_paise)} ${t('common.per_kg')}` : '—'}</dd>
      <dt>${t('market.total_value')}</dt>
      <dd>${m.target_price_paise
            ? money(Math.round(m.quantity_kg * m.target_price_paise))
            : '—'}</dd>
    </dl>

    ${scored && m.reasons?.length
      ? `<ul class="reasons">${m.reasons.map((r) => `<li>${r}</li>`).join('')}</ul>` : ''}
  </article>`;
}
