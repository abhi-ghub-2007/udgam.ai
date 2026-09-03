/* B-2 Product Detail + Checkout. */

import { api } from '../../core/api.js';
import { t, money, number, date } from '../../core/i18n.js';
import { store } from '../../core/store.js';
import { navigate } from '../../core/router.js';

export const title = 'market.detail_title';

let p = null;
let farmer = null;
let quality = null;

export async function render(params) {
  try {
    const res = await api.get(`/api/products/${params.id}`);
    p = res.product;
    farmer = res.farmer;
    quality = res.quality;
  } catch (err) {
    return `<div class="state state--error"><p class="state__body">${t('common.error_body')}</p></div>`;
  }

  const isAvailable = p.status === 'active' && p.available_quantity_kg > 0;
  const grade = (p.grade || 'c').toLowerCase();

  return `
  <div class="stack stack--lg">
    <div class="row row--between">
      <h1>${p.crop_name}</h1>
      ${p.grade ? `<span class="badge badge--grade-${grade}">${t(`product.grade_${grade}`)}</span>` : ''}
    </div>

    <section class="card">
      <dl class="meta">
        <dt>${t('product.quantity')}</dt><dd>${number(p.available_quantity_kg)} ${t('common.kg')} available</dd>
        <dt>${t('product.asking_price')}</dt><dd>${money(p.asking_price_paise)} ${t('common.per_kg')}</dd>
        <dt>Total Value</dt><dd>${money(p.asking_price_paise * p.available_quantity_kg)}</dd>
        <dt>Location</dt><dd>${farmer?.district || p.district}, ${farmer?.state || ''}</dd>
        <dt>Farmer</dt><dd>${farmer?.full_name || 'Farmer'} 
            ${farmer?.avg_rating ? `(★ ${farmer.avg_rating})` : ''}
            ${p.listed_by_fpo_id ? `<span class="badge">${t('product.listed_by_fpo')}</span>` : ''}
        </dd>
        ${p.harvest_date ? `<dt>${t('product.harvest_date')}</dt><dd>${date(p.harvest_date)}</dd>` : ''}
      </dl>
      ${p.description ? `<p style="margin-top:16px">${p.description}</p>` : ''}
    </section>

    ${quality ? `
    <section class="card insight">
      <div class="section-head">
        <h2>AI Quality Assessment</h2>
        <span class="badge">${t(`ai.method_${quality.method}`)}</span>
      </div>
      <p style="margin-bottom: 16px">The farmer provided a photo that was automatically graded.</p>
      <dl class="meta">
        <dt>Grade</dt><dd>${quality.grade}</dd>
        <dt>Confidence</dt><dd>${Math.round((quality.confidence || 0) * 100)}%</dd>
      </dl>
      <ul class="reasons" style="margin-top: 16px">
        ${(quality.reasons || []).map(r => `<li>${r}</li>`).join('')}
      </ul>
    </section>
    ` : ''}

    ${isAvailable ? `
    <section class="card" style="border-color: var(--c-primary)">
      <h2>Purchase Request</h2>
      <form id="purchase-form" class="stack stack--sm" style="margin-top: 16px">
        <div class="field">
          <label class="label">Quantity (kg)</label>
          <input type="number" id="qty" class="input" min="1" max="${p.available_quantity_kg}" value="${p.available_quantity_kg}" required />
        </div>
        
        <div class="field">
          <label class="label">Who will arrange transportation?</label>
          <select id="logistics" class="input" required>
            <option value="buyer">I will arrange transport (Buyer)</option>
            <option value="farmer">Farmer will arrange transport</option>
          </select>
          <p id="transport-hint" style="font-size: var(--fs-label); color: var(--c-ink-muted); margin-top: 4px;">
            You will be able to book transport from our marketplace after placing the order.
          </p>
        </div>

        <button type="submit" class="btn btn--primary btn--block">Send Purchase Request</button>
      </form>
    </section>
    ` : `
    <div class="state state--empty">
      <p class="state__body">This product is no longer available.</p>
    </div>
    `}
  </div>`;
}

export function mount() {
  const form = document.getElementById('purchase-form');
  const logistics = document.getElementById('logistics');
  const hint = document.getElementById('transport-hint');

  if (logistics) {
    const handleLogistics = () => {
      if (logistics.value === 'buyer') {
        hint.textContent = 'You will be able to book transport from our marketplace after placing the order.';
      } else {
        hint.textContent = 'Transportation will be arranged by the farmer. You just pay the final price.';
      }
    };
    logistics.addEventListener('change', handleLogistics);
  }

  if (form) {
    const onSubmit = async (e) => {
      e.preventDefault();
      const qty = parseFloat(document.getElementById('qty').value);
      const log = document.getElementById('logistics').value;

      if (qty > p.available_quantity_kg) {
        alert('Quantity cannot exceed available amount.');
        return;
      }

      const btn = form.querySelector('button');
      btn.disabled = true;
      btn.textContent = t('common.loading') + '...';

      try {
        const order = await api.post('/api/orders', {
          product_id: p.id,
          farmer_id: p.farmer_id,
          quantity_kg: qty,
          logistics_arranged_by: log
        });
        navigate('/buyer/orders', { replace: true });
      } catch (err) {
        btn.disabled = false;
        btn.textContent = 'Send Purchase Request';
        alert(err.message || 'Could not place order');
      }
    };
    form.addEventListener('submit', onSubmit);
    return () => form.removeEventListener('submit', onSubmit);
  }
}
