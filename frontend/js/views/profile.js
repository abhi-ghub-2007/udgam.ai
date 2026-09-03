/* C-1 profile. Edit own details, view own ratings, see verification status. */

import { api } from '../core/api.js';
import { supabase } from '../core/supabase.js';
import { store } from '../core/store.js';
import { t, setLang, applyTranslations, LANGS } from '../core/i18n.js';
import { toast } from '../core/toast.js';
import { refresh } from '../core/router.js';

export const title = 'nav.profile';

export function render() {
  const p = store.get('profile') || {};
  const isFpo = store.get('isFpo');

  return `
  <div class="stack stack--lg">
    <h1>${t('nav.profile')}</h1>

    <section class="card stack">
      <div class="row row--between">
        <span class="card__title">${p.full_name ?? ''}</span>
        <span class="badge badge--${p.verification_status === 'verified' ? 'success' : 'warning'}">
          ${t(`profile.verification.${p.verification_status || 'self_declared'}`)}
        </span>
      </div>
      <div class="card__meta">
        ${t(`auth.role_${p.role || 'farmer'}`)}${isFpo ? ' · FPO' : ''}
      </div>
      <div class="row">
        <span class="stat__value">${(p.avg_rating ?? 0).toFixed(1)}</span>
        <span class="card__meta">${t('profile.rating_count', { n: p.rating_count ?? 0 })}</span>
      </div>
    </section>

    <form id="profile-form" class="card stack" novalidate>
      <div class="field">
        <label class="field__label" for="full_name">${t('auth.full_name')}</label>
        <input class="input" id="full_name" name="full_name" value="${p.full_name ?? ''}" required>
      </div>
      <div class="field">
        <label class="field__label" for="phone">${t('auth.phone')}</label>
        <input class="input" id="phone" name="phone" type="tel" value="${p.phone ?? ''}">
      </div>
      <div class="field">
        <label class="field__label" for="district">${t('auth.district')}</label>
        <input class="input" id="district" name="district" value="${p.district ?? ''}">
      </div>
      <div class="field">
        <label class="field__label" for="pincode">${t('auth.pincode')}</label>
        <input class="input" id="pincode" name="pincode" inputmode="numeric" value="${p.pincode ?? ''}">
      </div>
      <div class="field">
        <label class="field__label" for="preferred_language">${t('common.language')}</label>
        <select class="select" id="preferred_language" name="preferred_language">
          ${LANGS.map((l) => `<option value="${l.code}" ${l.code === p.preferred_language ? 'selected' : ''}>${l.label}</option>`).join('')}
        </select>
      </div>
      <p id="profile-error" class="field__error" role="alert" hidden></p>
      <button class="btn btn--primary btn--block" type="submit" id="profile-save">${t('common.save')}</button>
    </form>

    <button class="btn btn--outline btn--block" id="sign-out">${t('auth.sign_out')}</button>
  </div>`;
}

export function mount(root) {
  const form = root.querySelector('#profile-form');
  const err = root.querySelector('#profile-error');
  const btn = root.querySelector('#profile-save');
  const out = root.querySelector('#sign-out');

  const onSubmit = async (e) => {
    e.preventDefault();
    err.hidden = true;
    btn.disabled = true;
    try {
      const body = {
        full_name: form.full_name.value.trim(),
        phone: form.phone.value.trim() || null,
        district: form.district.value.trim() || null,
        pincode: form.pincode.value.trim() || null,
        preferred_language: form.preferred_language.value,
      };
      const updated = await api.patch('/api/profiles/me', body);
      store.set('profile', updated.profile ?? { ...store.get('profile'), ...body });
      if (body.preferred_language !== store.get('lang')) {
        await setLang(body.preferred_language);
        applyTranslations();
        refresh();
      }
      toast(t('common.save'), 'success');
    } catch (ex) {
      err.textContent = ex.message;
      err.hidden = false;
    } finally {
      btn.disabled = false;
    }
  };

  const onSignOut = async () => { await supabase.auth.signOut(); };

  form.addEventListener('submit', onSubmit);
  out.addEventListener('click', onSignOut);
  return () => {
    form.removeEventListener('submit', onSubmit);
    out.removeEventListener('click', onSignOut);
  };
}
