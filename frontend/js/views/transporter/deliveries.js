/* T-4 Delivery Details & Status Update */

import { api } from '../../core/api.js';
import { t, money } from '../../core/i18n.js';

export const title = 'Delivery Details';

let shipments = [];
let shipment = null;

export async function render(params) {
  try {
    const res = await api.get('/api/shipments');
    shipments = res.shipments || [];
    shipment = shipments.find(s => s.id === params.id);
  } catch (err) {
    return `<div class="state state--error"><p class="state__body">${t('common.error_body')}</p></div>`;
  }

  if (!shipment) {
    return `<div class="state state--empty"><p class="state__body">Delivery not found.</p></div>`;
  }

  const isAssigned = shipment.status === 'assigned';
  const isPickedUp = shipment.status === 'picked_up';
  const isInTransit = shipment.status === 'in_transit';
  const isDelivered = shipment.status === 'delivered';

  return `
  <div class="stack stack--lg">
    <h1>Order ${shipment.order_no}</h1>
    
    <section class="card insight">
      <div class="row row--between">
        <h2>Shipment Status</h2>
        <span class="badge">${shipment.status.toUpperCase().replace('_', ' ')}</span>
      </div>
      <dl class="meta" style="margin-top: 16px">
        <dt>Order Status</dt><dd>${t(`order.status.${shipment.order_status}`)}</dd>
        <dt>Est. Earnings</dt><dd>${money(shipment.earnings_paise || 0)}</dd>
      </dl>
    </section>

    <section class="card">
      <h2>Update Status</h2>
      <div class="stack stack--sm" style="margin-top: 16px">
        ${isAssigned ? `
          <button class="btn btn--primary" id="btn-pickup">Confirm Pickup</button>
        ` : ''}
        
        ${isPickedUp ? `
          <button class="btn btn--primary" id="btn-transit">Mark In Transit</button>
        ` : ''}
        
        ${isInTransit ? `
          <div class="field">
            <label class="label">Enter Buyer's OTP (Mock: 123456)</label>
            <input type="text" id="otp" class="input" placeholder="6-digit OTP" />
          </div>
          <button class="btn btn--primary btn--block" id="btn-deliver">Confirm Delivery & Release Escrow</button>
        ` : ''}

        ${isDelivered ? `
          <div class="state state--empty" style="margin-top:0"><p class="state__body">This delivery is completed. The payment has been released to your account.</p></div>
        ` : ''}
      </div>
    </section>
  </div>`;
}

export function mount() {
  const handleStatus = async (btn, status) => {
    btn.disabled = true;
    btn.textContent = t('common.loading') + '...';
    
    if (status === 'delivered') {
      const otp = document.getElementById('otp').value;
      if (otp !== '123456') {
        alert('Invalid OTP for demo. Please use 123456.');
        btn.disabled = false;
        btn.textContent = 'Confirm Delivery & Release Escrow';
        return;
      }
    }

    try {
      await api.post(`/api/shipments/${shipment.id}/status`, { status });
      window.location.reload();
    } catch (err) {
      btn.disabled = false;
      alert(err.message || 'Failed to update status');
    }
  };

  const btnPickup = document.getElementById('btn-pickup');
  if (btnPickup) {
    const fn = (e) => handleStatus(e.currentTarget, 'picked_up');
    btnPickup.addEventListener('click', fn);
    return () => btnPickup.removeEventListener('click', fn);
  }
  
  const btnTransit = document.getElementById('btn-transit');
  if (btnTransit) {
    const fn = (e) => handleStatus(e.currentTarget, 'in_transit');
    btnTransit.addEventListener('click', fn);
    return () => btnTransit.removeEventListener('click', fn);
  }
  
  const btnDeliver = document.getElementById('btn-deliver');
  if (btnDeliver) {
    const fn = (e) => handleStatus(e.currentTarget, 'delivered');
    btnDeliver.addEventListener('click', fn);
    return () => btnDeliver.removeEventListener('click', fn);
  }
}
