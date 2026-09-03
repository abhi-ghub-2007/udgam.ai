/* F-2 / AI-1: list produce, then grade it from a photo.

   Two real backend calls, in order:
     POST /api/products              -> creates the listing
     POST /api/products/{id}/photo   -> runs AI-1 server-side, returns the grade
   The grade is never computed in the browser. The farmer sees the result and
   confirms before leaving the flow (1D). */

import { api } from '../../core/api.js';
import { t, money, getLang } from '../../core/i18n.js';
import { toast } from '../../core/toast.js';
import { navigate } from '../../core/router.js';

export const title = 'market.new_listing_title';

let crops = [];

// Three shots, each with a stated purpose, so the farmer knows what to take.
const SHOTS = [
  { id: 'shot-batch',   key: 'market.shot_batch' },
  { id: 'shot_size',    key: 'market.shot_size' },
  { id: 'shot_quality', key: 'market.shot_quality' },
];

export async function render() {
  try {
    // /api/crops answers with {items:[...]} (API_CONTRACT §2).
    ({ items: crops } = await api.get('/api/crops'));
  } catch {
    crops = [];
  }

  const today = new Date().toISOString().slice(0, 10);

  const lang = getLang();
  const cropLabel = (c) => c[`name_${lang}`] || c.name_en;

  return `
  <div class="stack stack--lg">
    <h1>${t('market.new_listing_title')}</h1>

    <form id="listing-form" class="card--ambient stack" style="padding:var(--sp-lg)" novalidate>
      <div class="field">
        <label class="field__label" for="crop_id">${t('market.crop')}</label>
        <select class="input" id="crop_id" name="crop_id" required>
          <option value="">—</option>
          ${crops.map((c) => `<option value="${c.id}">${cropLabel(c)}</option>`).join('')}
        </select>
      </div>

      <div class="row" style="gap:var(--sp-md)">
        <div class="field" style="flex:1;min-width:140px">
          <label class="field__label" for="quantity_kg">${t('market.quantity_kg')}</label>
          <input class="input" id="quantity_kg" name="quantity_kg" type="number"
                 inputmode="decimal" min="1" step="1" required>
        </div>
        <div class="field" style="flex:1;min-width:140px">
          <label class="field__label" for="price">${t('market.price_per_kg')}</label>
          <input class="input" id="price" name="price" type="number"
                 inputmode="decimal" min="1" step="0.5" required>
        </div>
      </div>

      <div class="row" style="gap:var(--sp-md)">
        <div class="field" style="flex:1;min-width:140px">
          <label class="field__label" for="harvest_date">${t('market.harvest_date')}</label>
          <input class="input" id="harvest_date" name="harvest_date" type="date" value="${today}">
        </div>
        <div class="field" style="flex:1;min-width:140px">
          <label class="field__label" for="available_until">${t('market.available_until')}</label>
          <input class="input" id="available_until" name="available_until" type="date">
        </div>
      </div>

      <div class="field">
        <label class="field__label" for="district">${t('auth.district')}</label>
        <input class="input" id="district" name="district" autocomplete="address-level2">
        <span class="field__hint">${t('market.district_hint')}</span>
      </div>

      <div class="field">
        <label class="field__label" for="description">${t('market.description')}</label>
        <textarea class="input" id="description" name="description" rows="2"></textarea>
      </div>

      <fieldset class="field" style="border:0;padding:0;margin:0">
        <legend class="field__label">${t('market.photos')}</legend>
        <div class="shots">
          ${SHOTS.map((s) => `
            <label class="shot" for="${s.id}">
              <span data-slot-text>${t(s.key)}</span>
              <input type="file" id="${s.id}" accept="image/*" data-slot>
            </label>`).join('')}
        </div>
        <span class="field__hint">${t('market.photos_hint')}</span>
      </fieldset>

      <p id="form-error" class="field__error" role="alert" hidden></p>

      <button class="btn btn--primary btn--block" type="submit" id="submit">
        ${t('market.submit_listing')}
      </button>
    </form>

    <section id="grade-panel" hidden></section>
  </div>`;
}

export function mount(root) {
  const form = root.querySelector('#listing-form');
  const err = root.querySelector('#form-error');
  const btn = root.querySelector('#submit');
  const panel = root.querySelector('#grade-panel');

  const fail = (msg, field) => {
    err.textContent = msg;
    err.hidden = false;
    field?.focus();
    return false;
  };

  // Preview each photo in its own slot so the farmer can see what was picked.
  const onFile = (e) => {
    const input = e.target.closest('[data-slot]');
    if (!input?.files?.[0]) return;
    const slot = input.closest('.shot');
    const url = URL.createObjectURL(input.files[0]);
    slot.querySelector('img')?.remove();
    const img = document.createElement('img');
    img.src = url;
    img.alt = '';
    img.onload = () => URL.revokeObjectURL(url);
    slot.prepend(img);
  };

  const onSubmit = async (e) => {
    e.preventDefault();
    err.hidden = true;

    const cropId = form.crop_id.value;
    const qty = parseFloat(form.quantity_kg.value);
    const priceRupees = parseFloat(form.price.value);
    if (!cropId) return fail(t('market.err_crop'), form.crop_id);
    if (!(qty > 0)) return fail(t('market.err_quantity'), form.quantity_kg);
    if (!(priceRupees > 0)) return fail(t('market.err_price'), form.price);

    const photo = [...form.querySelectorAll('[data-slot]')]
      .map((i) => i.files?.[0]).find(Boolean);

    btn.disabled = true;
    btn.textContent = t('common.loading');

    try {
      const product = await api.post('/api/products', {
        crop_id: cropId,
        quantity_kg: qty,
        // Paise, integer — money is never a float anywhere in UDGAM (A-6).
        asking_price_paise: Math.round(priceRupees * 100),
        harvest_date: form.harvest_date.value || null,
        available_until: form.available_until.value || null,
        description: form.description.value.trim() || null,
        district: form.district.value.trim() || null,
      });

      if (!photo) {
        toast(t('market.listing_created'), 'success');
        return navigate(`/farmer/listings/${product.id}`, { replace: true });
      }

      btn.textContent = t('market.grading');
      const body = new FormData();
      body.append('file', photo);
      const grade = await api.postForm(`/api/products/${product.id}/photo`, body);

      panel.hidden = false;
      panel.innerHTML = gradePanel(grade, product);
      panel.scrollIntoView({ behavior: 'smooth', block: 'start' });
      form.hidden = true;
    } catch (ex) {
      btn.disabled = false;
      btn.textContent = t('market.submit_listing');
      fail(ex.message || t('common.error_body'));
    }
  };

  form.addEventListener('change', onFile);
  form.addEventListener('submit', onSubmit);

  const onPanel = (e) => {
    const go = e.target.closest('[data-action="confirm-grade"]');
    if (go) navigate(`/farmer/listings/${go.dataset.id}`, { replace: true });
  };
  panel.addEventListener('click', onPanel);

  return () => {
    form.removeEventListener('change', onFile);
    form.removeEventListener('submit', onSubmit);
    panel.removeEventListener('click', onPanel);
  };
}

/** The AI-1 result, with its honesty label and the feature breakdown that
    makes the grade auditable rather than magic (PRD §13 step 2). */
function gradePanel(g, product) {
  const pct = Math.round((g.confidence || 0) * 100);
  const f = g.features || {};
  return `
  <div class="insight stack">
    <span class="insight__eyebrow">
      ${t('ai.method')}: ${t(`ai.method_${g.method}`)}
    </span>
    <h2 class="insight__title">${t(`market.quality_${String(g.grade).toLowerCase()}`)}</h2>
    <p class="insight__body">${t('ai.confidence')}: ${pct}%</p>

    ${f.score != null ? `<p class="insight__body"><strong>${t('market.composite_score')}</strong>: ${f.score}/100</p>` : ''}
    <ul class="reasons">${(g.reasons || f.explanations || []).map((r) => `<li>${r}</li>`).join('')}</ul>

    <dl class="meta">
      <dt>${t('market.f_colour')}</dt><dd>${f.color_score != null ? f.color_score + '/100' : (f.mean_sat ?? '—')}</dd>
      <dt>${t('market.f_blemish')}</dt><dd>${f.blemish_score != null ? f.blemish_score + '/100' : (f.blemish_ratio != null ? (f.blemish_ratio * 100).toFixed(1) + '%' : '—')}</dd>
      <dt>${t('market.f_shape')}</dt><dd>${f.shape_score != null ? f.shape_score + '/100' : (f.size_consistency != null ? Math.round(f.size_consistency * 100) + '%' : '—')}</dd>
      <dt>${t('market.f_sharpness')}</dt><dd>${f.sharpness_score != null ? f.sharpness_score + '/100' : (f.laplacian_blur ?? '—')}</dd>
    </dl>

    <p class="insight__body">${t('market.quality_not_size')}</p>

    <button class="btn btn--primary btn--block" data-action="confirm-grade" data-id="${product.id}">
      ${t('market.confirm_grade')}
    </button>
  </div>`;
}

export { money };
