/* F-2 My Products. Backed by GET /api/products/mine.
   Every action here hits the real products API — there is no second
   product-management path in the app. */

import { api } from '../../core/api.js';
import { t, money, number } from '../../core/i18n.js';
import { toast } from '../../core/toast.js';
import { refresh } from '../../core/router.js';
import { produceCard } from './cards.js';

export const title = 'market.my_listings_title';

let products = [];

export async function render() {
  try {
    ({ products } = await api.get('/api/products/mine'));
  } catch {
    products = null;
  }

  if (products === null) {
    return `<div class="state state--error" role="alert">
      <h2 class="state__title">${t('common.error_title')}</h2>
      <p class="state__body">${t('common.error_body')}</p>
      <button class="btn btn--primary" data-action="reload">${t('common.retry')}</button>
    </div>`;
  }

  const live = products.filter((p) => p.status !== 'withdrawn');

  return `
  <div class="stack stack--lg">
    <div class="section-head">
      <h1>${t('market.my_listings_title')}</h1>
      <a class="btn btn--primary" href="#/farmer/listings/new">${t('market.list_new')}</a>
    </div>

    ${live.length ? `<div class="grid">${live.map(produceCard).join('')}</div>` : `
      <div class="state state--empty">
        <p class="state__body">${t('market.empty_listings')}</p>
        <a class="btn btn--primary" href="#/farmer/listings/new">${t('market.list_new')}</a>
      </div>`}

    ${products.some((p) => p.status === 'withdrawn') ? `
      <section class="stack stack--sm">
        <h2>${t('market.withdrawn')}</h2>
        <div class="grid">
          ${products.filter((p) => p.status === 'withdrawn').map(produceCard).join('')}
        </div>
      </section>` : ''}
  </div>`;
}

export function mount(root) {
  const onClick = async (e) => {
    if (e.target.closest('[data-action="reload"]')) return refresh();

    const btn = e.target.closest('[data-action="withdraw"]');
    if (!btn) return;
    e.preventDefault();                 // the card itself is a link
    const { id, name } = btn.dataset;
    if (!confirm(t('market.confirm_withdraw', { name }))) return;

    btn.disabled = true;
    try {
      await api.delete(`/api/products/${id}`);
      toast(t('market.withdraw_done', { name }), 'success');
      refresh();
    } catch (ex) {
      toast(ex.message || t('common.error_body'), 'error');
      btn.disabled = false;
    }
  };

  root.addEventListener('click', onClick);
  return () => root.removeEventListener('click', onClick);
}

export { number, money };
