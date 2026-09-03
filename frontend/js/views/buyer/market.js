/* B-1 Marketplace — find produce. */

import { api } from '../../core/api.js';
import { t, money, number, getLang } from '../../core/i18n.js';

export const title = 'market.browse_title';

let products = [];
let crops = [];

export async function render() {
  const [p, c] = await Promise.allSettled([
    api.get('/api/products?status=active'),
    api.get('/api/crops'),
  ]);
  
  if (p.status === 'fulfilled') products = p.value.products || [];
  if (c.status === 'fulfilled') crops = c.value.items || [];

  const lang = getLang();
  const cropLabel = (crop) => crop[`name_${lang}`] || crop.name_en;

  return `
  <div class="stack stack--lg">
    <h1>${t('market.browse_title')}</h1>
    
    <div class="filter-bar">
      <select id="f-crop" class="input">
        <option value="">All crops</option>
        ${crops.map(crop => `<option value="${crop.id}">${cropLabel(crop)}</option>`).join('')}
      </select>
      <select id="f-grade" class="input">
        <option value="">All grades</option>
        <option value="A">Grade A</option>
        <option value="B">Grade B</option>
        <option value="C">Grade C</option>
      </select>
      <input type="number" id="f-max-price" class="input" placeholder="Max price / kg" />
      <button class="btn btn--secondary" id="btn-filter">${t('common.filter')}</button>
    </div>

    <section class="grid" id="market-grid">
      ${renderGrid(products)}
    </section>
  </div>`;
}

function renderGrid(list) {
  if (!list.length) return `<div class="state state--empty"><p class="state__body">${t('market.empty_listings')}</p></div>`;
  return list.map(card).join('');
}

function card(p) {
  const grade = (p.grade || 'c').toLowerCase();
  return `<a class="card card--interactive" href="#/buyer/product/${p.id}">
    <div class="row row--between">
      <span class="card__title">${p.crop_name}</span>
      ${p.grade ? `<span class="badge badge--grade-${grade}">${t(`product.grade_${grade}`)}</span>` : ''}
    </div>
    <div class="card__meta">${number(p.quantity_kg)} ${t('common.kg')} · ${money(p.asking_price_paise)} ${t('common.per_kg')}</div>
    <div class="card__meta">${p.district ?? ''}</div>
  </a>`;
}

export function mount() {
  const btn = document.getElementById('btn-filter');
  const hnd = async () => {
    const crop_id = document.getElementById('f-crop').value || undefined;
    const grade = document.getElementById('f-grade').value || undefined;
    const maxPriceRaw = document.getElementById('f-max-price').value;
    const max_price = maxPriceRaw ? Math.round(parseFloat(maxPriceRaw) * 100) : undefined;
    
    btn.disabled = true;
    try {
      const res = await api.get('/api/products', { crop_id, grade, max_price });
      document.getElementById('market-grid').innerHTML = renderGrid(res.products || []);
    } finally {
      btn.disabled = false;
    }
  };
  btn?.addEventListener('click', hnd);
  return () => btn?.removeEventListener('click', hnd);
}
