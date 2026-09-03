/* ===========================================================================
   app.js - bootstrap. Wires config -> i18n -> supabase -> session -> router.
   =========================================================================== */

import { initSupabase, supabase } from './core/supabase.js';
import { initI18n, setLang, applyTranslations, LANGS, t, getLang } from './core/i18n.js';
import { store, cache } from './core/store.js';
import { startRouter, navigate, refresh } from './core/router.js';
import { renderNav, mountNav } from './core/nav.js';
import { toast } from './core/toast.js';
import { api } from './core/api.js';
import { registerRoutes } from './routes.js?v=2';

const API_BASE = window.__UDGAM_API_BASE__ || 'http://127.0.0.1:8001';

function buildLangSwitcher() {
  const sel = document.getElementById('lang-select');
  sel.innerHTML = LANGS.map(
    (l) => `<option value="${l.code}">${l.label}</option>`,
  ).join('');
  sel.value = getLang();
  sel.addEventListener('change', async (e) => {
    await setLang(e.target.value);
    applyTranslations();
    renderNav();
    refresh();                       // re-render the current view in the new language
  });
}

async function loadSession() {
  const { data } = await supabase.auth.getSession();
  store.set('session', data?.session || null);
  if (!data?.session) {
    store.patch({ profile: null, details: null, isFpo: false });
    return null;
  }
  try {
    const me = await api.get('/api/auth/me');
    store.patch({ profile: me.profile, details: me.details, isFpo: me.is_fpo });
    if (me.profile?.preferred_language && me.profile.preferred_language !== getLang()) {
      await setLang(me.profile.preferred_language);
      applyTranslations();
    }
    return me;
  } catch (err) {
    // A session with no profile row means signup never finished.
    if (err.code === 'UNAUTHENTICATED' || err.code === 'NOT_FOUND') {
      store.patch({ profile: null, details: null });
    }
    return null;
  }
}

function reflectChrome() {
  const signedIn = !!store.get('session') && !!store.get('profile');
  document.getElementById('app-header').hidden = !signedIn;
  document.getElementById('bottom-nav').hidden = !signedIn;
  document.getElementById('voice-fab').hidden = !signedIn;
}

function watchOffline() {
  const banner = document.getElementById('stale-banner');
  const sync = () => {
    const offline = !store.get('online');
    banner.hidden = !(offline || store.get('stale'));
  };
  store.on('online', sync);
  store.on('stale', sync);
  sync();
}

async function boot() {
  await initI18n();
  buildLangSwitcher();
  applyTranslations();
  watchOffline();

  let cfg;
  try {
    cfg = await initSupabase(API_BASE);
  } catch (err) {
    console.error('[boot] initSupabase failed:', err);
    document.getElementById('main').innerHTML = `
      <div class="state state--error" role="alert">
        <h2 class="state__title">${t('common.api_down_title')}</h2>
        <p class="state__body">${t('common.api_down_body')}</p>
        <button class="btn btn--primary" onclick="location.reload()">${t('common.retry')}</button>
      </div>`;
    return;
  }

  if (!cfg.configured) {
    document.getElementById('main').innerHTML = `
      <div class="state state--error" role="alert">
        <h2 class="state__title">${t('common.setup_title')}</h2>
        <p class="state__body">${t('common.setup_body')}</p>
      </div>`;
    return;
  }

  registerRoutes();
  await loadSession();
  reflectChrome();
  renderNav();
  mountNav();

  supabase.auth.onAuthStateChange(async (event, session) => {
    if (event === 'SIGNED_OUT') {
      console.log('[auth] User signed out');
      store.patch({ session: null, profile: null, details: null, isFpo: false });
      cache.clear();
      reflectChrome();
      renderNav();
      return navigate('/login', { replace: true });
    }
    if (event === 'SIGNED_IN') {
      console.log('[auth] User signed in');
      if (session) store.set('session', session);
      if (location.hash.startsWith('#/signup')) return;
      await loadSession();
      reflectChrome();
      renderNav();
    }
    if (event === 'TOKEN_REFRESHED') {
      console.log('[auth] Token refreshed');
      if (session) store.set('session', session);
    }
  });

  store.on('profile', () => { reflectChrome(); renderNav(); });

  // Sign out is rendered by nav.js into the side rail, which re-renders on
  // every hashchange — so the listener is delegated from document, once.
  document.addEventListener('click', async (e) => {
    if (!e.target.closest('[data-action="sign-out"]')) return;
    
    e.preventDefault();
    try {
      // Sign out from Supabase
      const { error } = await supabase.auth.signOut();
      if (error) {
        console.error('[auth] Sign-out error:', error);
        toast(t('auth.signout_failed'), 'error');
        return;
      }
      
      // Clear all local state
      cache.clear();
      store.patch({ 
        session: null, 
        profile: null, 
        details: null, 
        isFpo: false,
        unreadCount: 0
      });
      
      // Force navigate to login
      navigate('/login', { replace: true });
      toast(t('auth.signout_success'), 'success');
    } catch (err) {
      console.error('[auth] Unexpected sign-out error:', err);
      toast(t('auth.signout_failed'), 'error');
    }
  });

  await startRouter(document.getElementById('main'));

  // Land signed-in users on their own dashboard rather than the marketing page.
  const role = store.get('profile')?.role;
  if (role && (location.hash === '' || location.hash === '#/')) {
    navigate(`/${role}`, { replace: true });
  }
}

boot().catch((err) => {
  console.error('[boot]', err);
  toast(t('common.error_body'), 'error');
});
