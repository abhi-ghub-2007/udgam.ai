/* T-3 Job Detail & Accept */

import { api } from '../../core/api.js';
import { t, money, date } from '../../core/i18n.js';
import { navigate } from '../../core/router.js';

export const title = 'Job Details';

let order = null;

export async function render(params) {
  try {
    const res = await api.get(`/api/orders/${params.id}`);
    order = res.order;
  } catch (err) {
    return `<div class="state state--error"><p class="state__body">${t('common.error_body')}</p></div>`;
  }

  return `
  <div class="stack stack--lg">
    <h1>Order ${order.order_no}</h1>
    
    <section class="card">
      <dl class="meta">
        <dt>Status</dt><dd>${t(`order.status.${order.status}`)}</dd>
        <dt>${t('transporter.cargo_value')}</dt><dd>${money(order.subtotal_paise)}</dd>
        <dt>${t('transporter.pickup_pincode')}</dt><dd>${t('transporter.available_after_accept')}</dd>
        <dt>${t('transporter.drop_pincode')}</dt><dd>${order.delivery_pincode || t('transporter.available_after_accept')}</dd>
        ${order.needed_by ? `<dt>Needed By</dt><dd>${date(order.needed_by)}</dd>` : ''}
      </dl>
    </section>

    <section class="card" style="border-color: var(--c-primary)">
      <h2>${t('transporter.accept_job')}</h2>
      <p style="margin-top: 4px; color: var(--c-ink-muted)">
        ${t('transporter.accept_job_desc')}
      </p>
      <button class="btn btn--primary btn--block" id="btn-accept" style="margin-top: 16px">
        ${t('transporter.accept_job')}
      </button>
    </section>
  </div>`;
}

export function mount() {
  const btn = document.getElementById('btn-accept');
  if (btn) {
    const handleAccept = async () => {
      btn.disabled = true;
      btn.textContent = t('common.loading') + '...';
      try {
        await api.post(`/api/orders/${order.id}/assign-transport`, {});
        navigate('/transporter', { replace: true });
      } catch (err) {
        btn.disabled = false;
        btn.textContent = t('transporter.accept_job');
        alert(err.message || 'Failed to accept job. It may have been taken.');
      }
    };
    btn.addEventListener('click', handleAccept);
    return () => btn.removeEventListener('click', handleAccept);
  }
}
