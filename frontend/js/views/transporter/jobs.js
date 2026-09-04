/* T-2 Find Transport Jobs */

import { api } from '../../core/api.js';
import { t, money, date } from '../../core/i18n.js';
import { loadDashboard } from '../dashboard-common.js';

export const title = 'Available Jobs';

let jobs = [];

export async function render() {
  try {
    // We are reusing the dashboard's available_jobs feed for this prototype.
    const { data } = await loadDashboard('/api/dashboard/transporter', 'dash.transporter');
    jobs = data.available_jobs || [];
  } catch (err) {
    return `<div class="state state--error"><p class="state__body">${t('common.error_body')}</p></div>`;
  }

  return `
  <div class="stack stack--lg">
    <h1>Available Jobs</h1>
    
    <div class="filter-bar">
      <select id="f-district" class="input">
        <option value="">Any District</option>
      </select>
      <button class="btn btn--secondary" disabled>Filter</button>
    </div>

    <section class="grid">
      ${jobs.length 
        ? jobs.map(jobCard).join('')
        : `<div class="state state--empty"><p class="state__body">No jobs available right now.</p></div>`
      }
    </section>
  </div>`;
}

function jobCard(job) {
  return `
  <article class="card card--interactive" data-job-id="${job.id}"
           role="link" tabindex="0" style="cursor:pointer">
    <div class="row row--between">
      <h3 style="margin:0">Order ${job.order_no}</h3>
      <span class="badge" style="background:var(--c-surface)">Needs Transport</span>
    </div>
    <div class="card__meta" style="margin-top:8px">
      ${job.needed_by ? `Needed by ${date(job.needed_by)}` : 'Flexible Date'}
    </div>
    <div class="card__meta">
      Cargo Value: ${money(job.subtotal_paise)}
    </div>
  </article>`;
}


export function mount(root) {
  // Delegated, per router.js: no inline handlers anywhere in a view.
  const go = (e) => {
    const card = e.target.closest('[data-job-id]');
    if (card) location.hash = `#/transporter/jobs/${card.dataset.jobId}`;
  };
  const keys = (e) => {
    if (e.key !== 'Enter' && e.key !== ' ') return;
    const card = e.target.closest('[data-job-id]');
    if (card) { e.preventDefault(); location.hash = `#/transporter/jobs/${card.dataset.jobId}`; }
  };
  root.addEventListener('click', go);
  root.addEventListener('keydown', keys);
  return () => { root.removeEventListener('click', go); root.removeEventListener('keydown', keys); };
}
