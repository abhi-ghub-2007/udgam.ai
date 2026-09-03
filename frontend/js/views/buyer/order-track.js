/* B-5 Order Tracking & Payment. */

import { api } from '../../core/api.js';
import { t, money, date } from '../../core/i18n.js';
import { store } from '../../core/store.js';

export const title = 'order.track_title';

let order = null;
let items = [];
let timeline = [];
let breakdown = null;
let farmer = null;

export async function render(params) {
  try {
    const res = await api.get(`/api/orders/${params.id}`);
    order = res.order;
    items = res.items || [];
    timeline = res.timeline || [];
    farmer = res.farmer || {};
    
    // Fetch breakdown
    const bRes = await api.get(`/api/orders/${params.id}/breakdown`);
    breakdown = bRes;
  } catch (err) {
    return `<div class="state state--error"><p class="state__body">${t('common.error_body')}</p></div>`;
  }

  const item = items[0] || {};
  const isAccepted = order.status === 'ACCEPTED';
  const isDelivered = order.status === 'DELIVERED';
  const inTransit = order.status === 'IN_TRANSIT' || order.status === 'PICKED_UP';

  return `
  <div class="stack stack--lg">
    <h1>Order ${order.order_no}</h1>
    
    <div class="card insight">
      <div class="row row--between">
        <h2>${item.crop_name || 'Produce'}</h2>
        <span class="badge" style="background:var(--c-surface)">${t(`order.status.${order.status}`)}</span>
      </div>
      <p style="margin-top: 4px; color: var(--c-ink-muted)">
        ${item.quantity_kg} ${t('common.kg')} · Farmer: ${farmer.full_name || '—'}
      </p>
    </div>

    ${isAccepted ? `
    <section class="card" style="border-color: var(--c-primary)">
      <h2>Payment Required</h2>
      <p style="margin-top: 4px; color: var(--c-ink-muted)">
        The farmer has accepted your order. Please pay the total amount into the UDGAM Escrow to secure the produce and arrange transportation.
      </p>
      <button class="btn btn--primary btn--block" id="btn-pay" style="margin-top: 16px">
        Pay ${money(order.buyer_total_paise)} (Mock)
      </button>
    </section>
    ` : ''}

    ${inTransit ? `
    <section class="card" style="border-color: var(--c-primary); background: var(--c-surface-alt)">
      <h2>Delivery OTP</h2>
      <p style="margin-top: 4px; color: var(--c-ink-muted)">
        Please provide this OTP to the transporter upon delivery to release the payment.
      </p>
      <div style="font-size: 32px; font-weight: bold; letter-spacing: 4px; text-align: center; margin-top: 16px; padding: 16px; border: 2px dashed var(--c-ink); border-radius: var(--radius-sm)">
        123456
      </div>
    </section>
    ` : ''}

    ${isDelivered ? `
    <section class="card" style="border-color: var(--c-primary)">
      <h2>Order Delivered</h2>
      <p style="margin-top: 4px; color: var(--c-ink-muted)">
        The delivery was confirmed. The payment has been released to the farmer and transporter.
      </p>
      <button class="btn btn--secondary btn--block" id="btn-close" style="margin-top: 16px">
        Close Order
      </button>
    </section>
    ` : ''}

    <section class="card">
      <div class="section-head">
        <h2>Transparent Pricing</h2>
        <span class="badge">${t('market.breakdown')}</span>
      </div>
      <dl class="meta" style="margin-top: 16px">
        <dt>Produce Subtotal</dt><dd>${money(breakdown.subtotal_paise)}</dd>
        <dt>Platform Fee (2%)</dt><dd>${money(breakdown.platform_fee_paise)}</dd>
        <dt>Transport Cost</dt><dd>${money(breakdown.transport_cost_paise)}</dd>
        <hr style="margin: 8px 0; border: none; border-top: 1px solid var(--c-surface-alt)" />
        <dt><strong>Total Paid by Buyer</strong></dt><dd><strong>${money(breakdown.buyer_total_paise)}</strong></dd>
      </dl>
      <div style="margin-top: 16px; padding: 12px; background: var(--c-surface-alt); border-radius: var(--radius-sm);">
        <p style="font-size: var(--fs-label); color: var(--c-ink-muted);">
          <strong>Where does the money go?</strong><br>
          Farmer gets: ${money(breakdown.farmer_payout_paise)}<br>
          Logistics gets: ${money(breakdown.transport_cost_paise - breakdown.logistics_facilitation_fee_paise)}
        </p>
      </div>
    </section>

    <section class="card">
      <h2>Timeline</h2>
      <ul class="reasons" style="list-style: none; padding-left: 0; margin-top: 16px">
        ${timeline.map(tLog => `
          <li style="margin-bottom: 12px; padding-left: 16px; border-left: 2px solid var(--c-primary)">
            <strong>${t(`order.status.${tLog.to_status}`)}</strong><br>
            <span style="font-size: var(--fs-label); color: var(--c-ink-muted)">${date(tLog.created_at)}</span>
            ${tLog.note ? `<br><span style="font-size: var(--fs-label)">${tLog.note}</span>` : ''}
          </li>
        `).join('')}
      </ul>
    </section>
  </div>`;
}

export function mount() {
  const btnPay = document.getElementById('btn-pay');
  if (btnPay) {
    const handlePay = async () => {
      btnPay.disabled = true;
      btnPay.textContent = t('common.loading') + '...';
      try {
        await api.post(`/api/orders/${order.id}/pay`);
        window.location.reload();
      } catch (err) {
        btnPay.disabled = false;
        btnPay.textContent = 'Pay';
        alert(err.message || 'Payment failed');
      }
    };
    btnPay.addEventListener('click', handlePay);
    return () => btnPay.removeEventListener('click', handlePay);
  }

  const btnClose = document.getElementById('btn-close');
  if (btnClose) {
    const handleClose = async () => {
      btnClose.disabled = true;
      try {
        await api.post(`/api/orders/${order.id}/transition`, { to_status: 'CLOSED' });
        window.location.reload();
      } catch (err) {
        btnClose.disabled = false;
        alert(err.message || 'Failed to close order');
      }
    };
    btnClose.addEventListener('click', handleClose);
    return () => btnClose.removeEventListener('click', handleClose);
  }
}
