/* Shared farmer-side card markup. One definition, so a produce card looks the
   same on the dashboard, the listings page and search results. */

import { t, money, number } from '../../core/i18n.js';

const LEAF = `<svg viewBox="0 0 24 24" width="48" height="48" aria-hidden="true">
  <path fill="currentColor" d="M17 8C8 10 5.9 16.2 3.8 21.7l1.9.7.9-2.4c.5.2 1 .3 1.4.3 8 0 11-8 9-12-1 2-3 3-6 3Z"/></svg>`;

/** Grade badge, or an honest "not graded yet" chip. */
export function gradeBadge(p) {
  if (!p.grade) return `<span class="badge">${t('market.grade_pending')}</span>`;
  const g = String(p.grade).toLowerCase();
  return `<span class="badge badge--grade-${g}">${t(`product.grade_${g}`)}</span>`;
}

const STATUS_PIP = {
  active: '', reserved: 'produce__pip--muted', sold: 'produce__pip--muted',
  draft: 'produce__pip--muted', withdrawn: 'produce__pip--muted',
  expired: 'produce__pip--muted',
};

export function produceCard(p) {
  const qty = number(p.available_quantity_kg ?? p.quantity_kg);
  return `
  <a class="produce" href="#/farmer/listings/${p.id}">
    <div class="produce__media">
      ${p.photo_url
        ? `<img src="${p.photo_url}" alt="${p.crop_name || ''}" loading="lazy">`
        : LEAF}
      <span class="produce__pip ${STATUS_PIP[p.status] ?? ''}">${t(`market.status_${p.status}`)}</span>
    </div>
    <div class="produce__body">
      <div class="produce__row">
        <span class="produce__name">${p.crop_name || '—'}</span>
        ${gradeBadge(p)}
      </div>
      <div class="produce__row">
        <span style="color:var(--c-ink-muted)">${qty} ${t('common.kg')}</span>
        <span class="produce__price">${money(p.asking_price_paise)} ${t('common.per_kg')}</span>
      </div>
    </div>
  </a>`;
}
