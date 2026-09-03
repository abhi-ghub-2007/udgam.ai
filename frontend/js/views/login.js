/* login view. Supabase Auth runs in the browser (plan.md section 3);
   FastAPI never sees a password. ENHANCED: Better error handling, validation, and UX. */

import { supabase } from '../core/supabase.js';
import { store } from '../core/store.js';
import { navigate } from '../core/router.js';
import { t } from '../core/i18n.js';
import { toast } from '../core/toast.js';

export const title = 'auth.login_title';

export function render() {
  return `
  <div class="auth-page stack">
    <h1>${t('auth.login_title')}</h1>

    <form id="login-form" class="card stack" novalidate>
      <div class="field">
        <label class="field__label" for="email">${t('auth.email')}</label>
        <input class="input" id="email" name="email" type="email"
               autocomplete="email" required inputmode="email" 
               aria-describedby="email-error">
      </div>
      <p id="email-error" class="field__error" hidden></p>

      <div class="field">
        <label class="field__label" for="password">${t('auth.password')}</label>
        <input class="input" id="password" name="password" type="password"
               autocomplete="current-password" required 
               aria-describedby="password-error">
      </div>
      <p id="password-error" class="field__error" hidden></p>

      <p id="login-error" class="field__error" role="alert" hidden></p>

      <button class="btn btn--primary btn--block" type="submit" id="login-submit">
        ${t('auth.sign_in')}
      </button>
    </form>

    <p class="row row--between">
      <span>${t('auth.no_account')}</span>
      <a class="btn btn--ghost" href="#/signup">${t('auth.sign_up')}</a>
    </p>
  </div>`;
}

export function mount(root) {
  const form = root.querySelector('#login-form');
  const emailField = form.email;
  const passwordField = form.password;
  const err = root.querySelector('#login-error');
  const btn = root.querySelector('#login-submit');
  let isSubmitting = false;

  const clearErrors = () => {
    err.hidden = true;
    root.querySelectorAll('[id$="-error"]').forEach(e => e.hidden = true);
  };

  const validateForm = () => {
    clearErrors();
    let isValid = true;

    const email = emailField.value.trim();
    if (!email) {
      root.querySelector('#email-error').textContent = t('auth.email_required');
      root.querySelector('#email-error').hidden = false;
      isValid = false;
    } else if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
      root.querySelector('#email-error').textContent = t('auth.email_invalid');
      root.querySelector('#email-error').hidden = false;
      isValid = false;
    }

    const password = passwordField.value;
    if (!password) {
      root.querySelector('#password-error').textContent = t('auth.password_required');
      root.querySelector('#password-error').hidden = false;
      isValid = false;
    } else if (password.length < 8) {
      root.querySelector('#password-error').textContent = t('auth.password_min_length');
      root.querySelector('#password-error').hidden = false;
      isValid = false;
    }

    return isValid;
  };

  const onSubmit = async (e) => {
    e.preventDefault();
    
    if (isSubmitting || !validateForm()) return;
    
    isSubmitting = true;
    btn.disabled = true;
    const originalText = btn.textContent;
    btn.textContent = t('common.loading');

    try {
      const { error, data } = await supabase.auth.signInWithPassword({
        email: emailField.value.trim(),
        password: passwordField.value,
      });

      if (error) {
        // Map specific Supabase error codes to user-friendly messages
        const errorMsg = mapSupabaseError(error);
        err.textContent = errorMsg;
        err.hidden = false;
        toast(errorMsg, 'error');
        passwordField.value = '';
        passwordField.focus();
        return;
      }

      if (!data.session) {
        err.textContent = t('auth.login_failed_no_session');
        err.hidden = false;
        toast(t('auth.login_failed_no_session'), 'error');
        return;
      }

      // Success - clear form and navigate
      store.set('session', data.session);
      clearErrors();
      
      // app.js's onAuthStateChange will load the profile; go where they were headed.
      const target = store.get('redirectAfterLogin');
      store.set('redirectAfterLogin', null);
      navigate(target || '/', { replace: true });
      
    } catch (ex) {
      console.error('[login] Sign-in error:', ex);
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
    const code = error.status || error.message;
    if (code === 'invalid_credentials' || code.includes('invalid')) {
      return t('auth.invalid_credentials');
    }
    if (code.includes('throttled') || code.includes('too many')) {
      return t('auth.too_many_attempts');
    }
    if (code.includes('network') || code.includes('connection')) {
      return t('common.network_error');
    }
    return error.message || t('common.error_body');
  };

  // Clear field-level errors when user starts typing
  emailField.addEventListener('input', () => {
    root.querySelector('#email-error').hidden = true;
  });
  passwordField.addEventListener('input', () => {
    root.querySelector('#password-error').hidden = true;
  });

  form.addEventListener('submit', onSubmit);
  return () => {
    form.removeEventListener('submit', onSubmit);
    emailField.removeEventListener('input', null);
    passwordField.removeEventListener('input', null);
  };
}
