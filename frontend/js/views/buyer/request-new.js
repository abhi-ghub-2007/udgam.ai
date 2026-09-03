/* B-7 Post Requirement. */

import { api } from '../../core/api.js';
import { t, getLang } from '../../core/i18n.js';
import { navigate } from '../../core/router.js';

export const title = 'Post Requirement';

let crops = [];

export async function render() {
  try {
    ({ items: crops } = await api.get('/api/crops'));
  } catch (err) {
    crops = [];
  }

  const lang = getLang();
  const cropLabel = (c) => c[`name_${lang}`] || c.name_en;

  return `
  <div class="stack stack--lg">
    <h1>Post Crop Requirement</h1>
    <p style="color: var(--c-ink-muted)">Tell farmers what you need, and we'll automatically match you with the best options.</p>

    <form id="req-form" class="stack stack--md card" novalidate>
      <div class="field">
        <label class="label" for="crop">Crop</label>
        <select id="crop" name="crop" class="input" required>
          <option value="">Select Crop...</option>
          ${crops.map(c => `<option value="${c.id}">${cropLabel(c)}</option>`).join('')}
        </select>
      </div>

      <div class="field">
        <label class="label">Quantity (kg)</label>
        <input type="number" id="qty" class="input" min="1" required />
      </div>

      <div class="field">
        <label class="label">Target Price (per kg, optional)</label>
        <input type="number" id="price" class="input" min="1" />
      </div>

      <div class="field">
        <label class="label">Minimum Grade (optional)</label>
        <select id="grade" class="input">
          <option value="">Any Grade</option>
          <option value="A">Grade A</option>
          <option value="B">Grade B</option>
        </select>
      </div>

      <button type="submit" class="btn btn--primary btn--block">Post Requirement</button>
    </form>
  </div>`;
}

export function mount() {
  const form = document.getElementById('req-form');
  if (form) {
    const onSubmit = async (e) => {
      e.preventDefault();
      const btn = form.querySelector('button');
      btn.disabled = true;
      btn.textContent = t('common.loading') + '...';

      const price = document.getElementById('price').value;
      
      const payload = {
        crop_id: document.getElementById('crop').value,
        quantity_kg: parseFloat(document.getElementById('qty').value),
        target_price_paise: price ? parseFloat(price) * 100 : null,
        min_grade: document.getElementById('grade').value || null
      };

      try {
        await api.post('/api/buyer-requests', payload);
        navigate('/buyer/requests', { replace: true });
      } catch (err) {
        btn.disabled = false;
        btn.textContent = 'Post Requirement';
        alert(err.message || 'Could not post requirement');
      }
    };
    form.addEventListener('submit', onSubmit);
    return () => form.removeEventListener('submit', onSubmit);
  }
}
