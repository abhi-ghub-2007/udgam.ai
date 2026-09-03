/* signup view. Creates the Supabase Auth user in the browser, then calls
   POST /api/auth/register to build profiles + the role detail row. ENHANCED: Better validation & error handling. */

import { supabase } from '../core/supabase.js';
import { store } from '../core/store.js';
import { api } from '../core/api.js';
import { navigate } from '../core/router.js';
import { t, getLang } from '../core/i18n.js';
import { toast } from '../core/toast.js';

export const title = 'auth.signup_title';

export function render() {
  return `
  <div class="auth-page stack">
    <h1>${t('auth.signup_title')}</h1>

    <form id="signup-form" class="card stack" novalidate>
      <fieldset class="field" style="border:0;padding:0;margin:0">
        <legend class="field__label">${t('auth.role')}</legend>
        <div class="chip-row" role="radiogroup" id="role-group">
          <button type="button" class="chip" data-role="farmer"      aria-pressed="true">${t('auth.role_farmer')}</button>
          <button type="button" class="chip" data-role="buyer"       aria-pressed="false">${t('auth.role_buyer')}</button>
          <button type="button" class="chip" data-role="transporter" aria-pressed="false">${t('auth.role_transporter')}</button>
        </div>
      </fieldset>

      <div class="field">
        <label class="field__label" for="full_name">${t('auth.full_name')}</label>
        <input class="input" id="full_name" name="full_name" required autocomplete="name"
               minlength="2" maxlength="120" aria-describedby="full_name-error">
      </div>
      <p id="full_name-error" class="field__error" hidden></p>

      <div class="field">
        <label class="field__label" for="email">${t('auth.email')}</label>
        <input class="input" id="email" name="email" type="email" required
               autocomplete="email" inputmode="email" aria-describedby="email-error">
      </div>
      <p id="email-error" class="field__error" hidden></p>

      <div class="field">
        <label class="field__label" for="password">${t('auth.password')}</label>
        <input class="input" id="password" name="password" type="password"
               required minlength="8" autocomplete="new-password" aria-describedby="password-hint password-error">
        <span class="field__hint" id="password-hint">${t('auth.password_hint')}</span>
      </div>
      <p id="password-error" class="field__error" hidden></p>

      <div class="field">
        <label class="field__label" for="phone">${t('auth.phone')}</label>
        <input class="input" id="phone" name="phone" type="tel"
               autocomplete="tel" inputmode="tel" aria-describedby="phone-error">
      </div>
      <p id="phone-error" class="field__error" hidden></p>

      <div class="field">
        <label class="field__label" for="district">${t('auth.district')}</label>
        <input class="input" id="district" name="district" autocomplete="address-level2"
               aria-describedby="district-error">
      </div>
      <p id="district-error" class="field__error" hidden></p>

      <div class="field">
        <label class="field__label" for="pincode">${t('auth.pincode')}</label>
        <input class="input" id="pincode" name="pincode" inputmode="numeric"
               pattern="[0-9]{6}" autocomplete="postal-code" aria-describedby="pincode-error">
      </div>
      <p id="pincode-error" class="field__error" hidden></p>

      <p id="signup-error" class="field__error" role="alert" hidden></p>

      <button class="btn btn--primary btn--block" type="submit" id="signup-submit">
        ${t('auth.sign_up')}
      </button>
    </form>

    <p class="row row--between">
      <span>${t('auth.have_account')}</span>
      <a class="btn btn--ghost" href="#/login">${t('auth.sign_in')}</a>
    </p>
  </div>`;
}

export function mount(root) {
  const form = root.querySelector('#signup-form');
  const err = root.querySelector('#signup-error');
  const btn = root.querySelector('#signup-submit');
  const group = root.querySelector('#role-group');
  let role = 'farmer';
  let isSubmitting = false;

  const clearErrors = () => {
    err.hidden = true;
    root.querySelectorAll('[id$="-error"]').forEach(e => e.hidden = true);
  };

  const validateForm = () => {
    clearErrors();
    let isValid = true;

    const fullName = form.full_name.value.trim();
    if (!fullName) {
      root.querySelector('#full_name-error').textContent = t('auth.full_name_required');
      root.querySelector('#full_name-error').hidden = false;
      isValid = false;
    } else if (fullName.length < 2) {
      root.querySelector('#full_name-error').textContent = t('auth.full_name_min_length');
      root.querySelector('#full_name-error').hidden = false;
      isValid = false;
    }

    const email = form.email.value.trim();
    if (!email) {
      root.querySelector('#email-error').textContent = t('auth.email_required');
      root.querySelector('#email-error').hidden = false;
      isValid = false;
    } else if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
      root.querySelector('#email-error').textContent = t('auth.email_invalid');
      root.querySelector('#email-error').hidden = false;
      isValid = false;
    }

    const password = form.password.value;
    if (!password) {
      root.querySelector('#password-error').textContent = t('auth.password_required');
      root.querySelector('#password-error').hidden = false;
      isValid = false;
    } else if (password.length < 8) {
      root.querySelector('#password-error').textContent = t('auth.password_min_length');
      root.querySelector('#password-error').hidden = false;
      isValid = false;
    }

    const pincode = form.pincode.value.trim();
    if (pincode && !/^[0-9]{6}$/.test(pincode)) {
      root.querySelector('#pincode-error').textContent = t('auth.pincode_invalid');
      root.querySelector('#pincode-error').hidden = false;
      isValid = false;
    }

    return isValid;
  };

  const onRole = (e) => {
    const chip = e.target.closest('[data-role]');
    if (!chip) return;
    role = chip.dataset.role;
    group.querySelectorAll('[data-role]').forEach((c) =>
      c.setAttribute('aria-pressed', String(c === chip)));
  };

  const onSubmit = async (e) => {
    e.preventDefault();
    
    if (isSubmitting || !validateForm()) return;
    
    isSubmitting = true;
    btn.disabled = true;
    const originalText = btn.textContent;
    btn.textContent = t('common.loading');

    try {
      const email = form.email.value.trim();
      const password = form.password.value;

      // Step 1: Create Supabase Auth user
      const { data: signUpData, error: signUpError } = await supabase.auth.signUp({
        email,
        password,
      });
      
      if (signUpError) {
        throw new Error(mapSupabaseError(signUpError));
      }

      // Step 2: Get session (auto-confirmed or needs manual login)
      let session = signUpData?.session;
      if (!session) {
        const { data: loginData, error: loginErr } = await supabase.auth.signInWithPassword({
          email,
          password,
        });
        
        if (loginErr) {
          // Account likely created but needs email confirmation
          throw new Error(t('auth.check_email_confirmation'));
        }
        session = loginData?.session;
      }

      if (!session) {
        throw new Error(t('auth.signup_no_session'));
      }

      store.set('session', session);

      // Step 3: Call FastAPI to create profile
      const me = await api.post(
        '/api/auth/register',
        {
          role,
          full_name: form.full_name.value.trim(),
          phone: form.phone.value.trim() || null,
          district: form.district.value.trim() || null,
          pincode: form.pincode.value.trim() || null,
          preferred_language: getLang(),
          role_details: {},
        },
        session?.access_token ? { Authorization: `Bearer ${session.access_token}` } : {},
      );

      if (me?.profile) {
        store.patch({
          session: session,
          profile: me.profile,
          details: me.details,
          isFpo: me.is_fpo,
        });
      }

      clearErrors();
      navigate(`/${role}`, { replace: true });
      
    } catch (ex) {
      console.error('[signup] Error:', ex);
      const errorMsg = ex.message || t('common.error_body');
      err.textContent = errorMsg;
      err.hidden = false;
      toast(errorMsg, 'error');
    } finally {
      isSubmitting = false;
      btn.disabled = false;
      btn.textContent = originalText;
    }
  };

  const mapSupabaseError = (error) => {
    const msg = error.message || '';
    if (msg.includes('already registered') || msg.includes('user_already_exists')) {
      return t('auth.email_already_registered');
    }
    if (msg.includes('weak password')) {
      return t('auth.password_too_weak');
    }
    if (msg.includes('network') || msg.includes('connection')) {
      return t('common.network_error');
    }
    return msg || t('common.error_body');
  };

  // Clear field-level errors when user starts typing
  form.querySelectorAll('input').forEach(field => {
    field.addEventListener('input', () => {
      const errorId = `${field.id}-error`;
      const errorEl = root.querySelector(`#${errorId}`);
      if (errorEl) errorEl.hidden = true;
    });
  });

  group.addEventListener('click', onRole);
  form.addEventListener('submit', onSubmit);
  
  return () => {
    group.removeEventListener('click', onRole);
    form.removeEventListener('submit', onSubmit);
    form.querySelectorAll('input').forEach(field => {
      field.removeEventListener('input', null);
    });
  };
}
