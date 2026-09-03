/* F-2 product detail: the listing, its AI-1 quality assessment, and the open
   buyer requests ranked against it (AI-5). Both panels are real API calls;
   nothing on this screen is illustrative. */

import { api } from '../../core/api.js';
import { t, money, number } from '../../core/i18n.js';
import { toast } from '../../core/toast.js';
import { navigate, refresh } from '../../core/router.js';
import { gradeBadge } from './cards.js';

export const title = 'market.detail_title';

let data = null;
let matches = [];

export async function render({ id }) {
  try {
    data = await api.get(`/api/products/${id}`);
  } catch {
    return `<div class="state state--error" role="alert">
      <h2 class="state__title">${t('common.error_title')}</h2>
      <p class="state__body">${t('common.error_body')}</p>
      <a class="btn btn--primary" href="#/farmer/listings">${t('common.back')}</a>
    </div>`;
  }

  // Ranked buyer requests for this listing. A failure here must not blank the
  // whole page — the listing itself is still worth showing.
  try {
    ({ matches } = await api.get('/api/matching/requests', { product_id: id }));
  } catch {
    matches = [];
  }

  const p = data.product;
  const q = data.quality_grade;

  return `
  <div class="stack stack--lg">
    <a class="btn btn--ghost" href="#/farmer/listings">← ${t('common.back')}</a>

    <section class="card--ambient stack" style="padding:var(--sp-lg)">
      <div class="section-head">
        <h1 style="margin:0">${p.crop_name || '—'}</h1>
        ${gradeBadge(p)}
      </div>

      ${p.photo_url ? `<img src="${p.photo_url}" alt="${p.crop_name || ''}"
           style="width:100%;max-height:280px;object-fit:cover;border-radius:var(--r-lg)">` : ''}

      <dl class="meta">
        <dt>${t('market.available')}</dt>
        <dd>${number(p.available_quantity_kg)} ${t('common.kg')}</dd>
        <dt>${t('market.price_per_kg')}</dt>
        <dd>${money(p.asking_price_paise)}</dd>
        <dt>${t('market.total_value')}</dt>
        <dd>${money(Math.round((p.available_quantity_kg || 0) * (p.asking_price_paise || 0)))}</dd>
        <dt>${t('market.harvest_date')}</dt><dd>${p.harvest_date || '—'}</dd>
        <dt>${t('market.available_until')}</dt><dd>${p.available_until || '—'}</dd>
        <dt>${t('auth.district')}</dt><dd>${p.district || '—'}</dd>
        <dt>${t('market.status')}</dt><dd>${t(`market.status_${p.status}`)}</dd>
      </dl>

      ${p.description ? `<p style="color:var(--c-ink-muted)">${p.description}</p>` : ''}

      <div class="row" style="gap:var(--sp-sm)">
        <button class="btn btn--outline" data-action="withdraw" data-id="${p.id}">
          ${t('market.withdraw')}
        </button>
      </div>
    </section>

    ${q ? qualityPanel(q) : `
      <section class="state state--empty">
        <p class="state__body">${t('market.no_grade_yet')}</p>
      </section>`}

    <section class="stack stack--sm">
      <div class="section-head">
        <h2>${t('market.buyers_for_this')}</h2>
        <span class="badge">${t('ai.method_ALGORITHMIC')}</span>
      </div>
      ${matches.length
        ? matches.map(matchRow).join('')
        : `<div class="state state--empty"><p class="state__body">${t('market.no_matches')}</p></div>`}
    </section>
  </div>`;
}

function qualityPanel(q) {
  const f = q.features || {};
  const pct = Math.round((q.confidence || 0) * 100);
  return `
  <section class="insight stack">
    <span class="insight__eyebrow">${t('ai.method')}: ${t(`ai.method_${q.method}`)}</span>
    <h2 class="insight__title">${t(`market.quality_${String(q.grade).toLowerCase()}`)}</h2>
    <p class="insight__body">${t('ai.confidence')}: ${pct}%</p>
    ${f.score != null ? `<p class="insight__body"><strong>${t('market.composite_score')}</strong>: ${f.score}/100</p>` : ''}
    <dl class="meta">
      <dt>${t('market.f_colour')}</dt><dd>${f.color_score != null ? f.color_score + '/100' : (f.mean_sat ?? '—')}</dd>
      <dt>${t('market.f_blemish')}</dt><dd>${f.blemish_score != null ? f.blemish_score + '/100' : (f.blemish_ratio != null ? (f.blemish_ratio * 100).toFixed(1) + '%' : '—')}</dd>
      <dt>${t('market.f_shape')}</dt><dd>${f.shape_score != null ? f.shape_score + '/100' : (f.size_consistency != null ? Math.round(f.size_consistency * 100) + '%' : '—')}</dd>
      <dt>${t('market.f_sharpness')}</dt><dd>${f.sharpness_score != null ? f.sharpness_score + '/100' : (f.laplacian_blur ?? '—')}</dd>
    </dl>
    <p class="insight__body">${t('market.quality_not_size')}</p>
  </section>`;
}

function matchRow(m) {
  return `
  <article class="card--ambient match">
    <div class="match__head">
      <div>
        <h3 style="margin:0">${m.crop_name} · ${number(m.quantity_kg)} ${t('common.kg')}</h3>
        <p style="margin:4px 0 0;color:var(--c-ink-muted)">
          ${m.delivery_district || '—'}
          ${m.needed_by ? ` · ${t('market.needed_by')} ${m.needed_by}` : ''}
        </p>
      </div>
      <div class="match__score">
        <b>${Math.round(m.score)}</b><span>${t('market.match_score')}</span>
      </div>
    </div>
    <dl class="meta">
      <dt>${t('market.min_grade')}</dt><dd>${m.min_grade}</dd>
      <dt>${t('market.target_price')}</dt>
      <dd>${m.target_price_paise ? money(m.target_price_paise) : '—'}</dd>
    </dl>
    <ul class="reasons">${(m.reasons || []).map((r) => `<li>${r}</li>`).join('')}</ul>
  </article>`;
}

export function mount(root) {
  const onClick = async (e) => {
    const btn = e.target.closest('[data-action="withdraw"]');
    if (!btn) return;
    if (!confirm(t('market.confirm_withdraw', { name: data?.product?.crop_name || '' }))) return;
    btn.disabled = true;
    try {
      await api.delete(`/api/products/${btn.dataset.id}`);
      toast(t('market.withdraw_done', { name: data?.product?.crop_name || '' }), 'success');
      navigate('/farmer/listings', { replace: true });
    } catch (ex) {
      toast(ex.message || t('common.error_body'), 'error');
      btn.disabled = false;
    }
  };
  root.addEventListener('click', onClick);
  return () => root.removeEventListener('click', onClick);
}

export { refresh };
