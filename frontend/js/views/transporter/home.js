/* T-1 Transporter Dashboard. */

import { api } from '../../core/api.js';
import { t, money, date } from '../../core/i18n.js';
import { store } from '../../core/store.js';
import { loadDashboard, statCard, section, emptyState } from '../dashboard-common.js';

export const title = 'transporter.dashboard.title';

export async function render() {
  const profile = store.get('profile') || {};
  let d = {};
  try {
    ({ data: d } = await loadDashboard('/api/dashboard/transporter', 'dash.transporter'));
  } catch { d = {}; }

  return `
  <div class="stack stack--lg">
    <h1>${t('farmer.dashboard.greeting', { name: profile.full_name || 'Transporter' })}</h1>

    <section class="grid">
      ${statCard('Active Jobs', d.active_jobs ?? 0)}
      ${statCard('This Month', money(d.earnings_month_paise ?? 0))}
      ${statCard('Total Earnings', money(d.total_earnings_paise ?? 0))}
    </section>

    ${section('Available Jobs',
      d.available_jobs?.length
        ? `<div class="stack stack--sm">${d.available_jobs.map(jobCard).join('')}</div>`
        : emptyState('No jobs currently available.', '#/transporter/capacity/new', 'Post Empty Leg'))}

    ${section('Upcoming Pickups',
      d.upcoming_pickups?.length
        ? `<div class="stack stack--sm">${d.upcoming_pickups.map(pickupCard).join('')}</div>`
        : emptyState('No upcoming pickups.', '#/transporter/jobs', 'Find Jobs'))}
  </div>`;
}

function jobCard(job) {
  return `<a class="card card--interactive" href="#/transporter/jobs/${job.id}">
    <div class="row row--between">
      <span class="card__title">Order ${job.order_no}</span>
      <span class="badge" style="background:var(--c-surface)">Needs Transport</span>
    </div>
    <div class="card__meta">Value: ${money(job.subtotal_paise)}</div>
    <div class="card__meta">${job.needed_by ? `Needed by ${date(job.needed_by)}` : ''}</div>
  </a>`;
}

function pickupCard(p) {
  return `<a class="card card--interactive" href="#/transporter/deliveries/${p.id}">
    <div class="row row--between">
      <span class="card__title">Order ${p.order_no}</span>
      <span class="badge" style="background:var(--c-surface)">${t(`order.status.${p.order_status}`)}</span>
    </div>
    <div class="card__meta">Status: ${p.status.toUpperCase()}</div>
    <div class="card__meta">Est. Earnings: ${money(p.earnings_paise)}</div>
  </a>`;
}
