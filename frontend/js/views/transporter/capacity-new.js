/* T-6 Post Empty Leg / Scheduled Route */

import { api } from '../../core/api.js';
import { t } from '../../core/i18n.js';
import { route } from '../../core/router.js';

export const title = 'Post Capacity';

export async function render() {
  return `
  <div class="stack stack--lg">
    <h1>Post Capacity</h1>
    <p style="color: var(--c-ink-muted)">Reduce empty runs by posting your available capacity and route.</p>

    <form id="cap-form" class="stack stack--md card">
      <div class="field">
        <label class="label">Capacity Type</label>
        <select id="type" class="input" required>
          <option value="empty_leg">Empty Leg (Return Trip)</option>
          <option value="scheduled_route">Scheduled Route</option>
          <option value="on_demand">On Demand</option>
        </select>
      </div>

      <div class="field">
        <label class="label">Origin District</label>
        <input type="text" id="origin" class="input" required />
      </div>

      <div class="field">
        <label class="label">Destination District</label>
        <input type="text" id="dest" class="input" required />
      </div>

      <div class="field">
        <label class="label">Available Capacity (kg)</label>
        <input type="number" id="capacity" class="input" min="1" required />
      </div>
      
      <div class="field">
        <label class="label">Discount for Empty Leg (%)</label>
        <input type="number" id="discount" class="input" min="0" max="100" value="0" />
      </div>

      <button type="submit" class="btn btn--primary btn--block">Post Route</button>
    </form>
  </div>`;
}

export function mount() {
  const form = document.getElementById('cap-form');
  if (form) {
    const onSubmit = async (e) => {
      e.preventDefault();
      const btn = form.querySelector('button');
      btn.disabled = true;
      btn.textContent = t('common.loading') + '...';
      
      const payload = {
        capacity_type: document.getElementById('type').value,
        origin_district: document.getElementById('origin').value,
        dest_district: document.getElementById('dest').value,
        total_capacity_kg: parseFloat(document.getElementById('capacity').value),
        discount_pct: parseFloat(document.getElementById('discount').value || 0)
      };

      try {
        await api.post('/api/transport/capacity', payload);
        route('/transporter/capacity');
      } catch (err) {
        btn.disabled = false;
        btn.textContent = 'Post Route';
        alert(err.message || 'Could not post capacity');
      }
    };
    form.addEventListener('submit', onSubmit);
    return () => form.removeEventListener('submit', onSubmit);
  }
}
