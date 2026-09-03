/* ===========================================================================
   router.js - hash router (PRD section 5.1).
   Views are pure functions: render(params) -> html string, and an optional
   mount(root, params) that attaches DELEGATED listeners. No view touches
   another view's DOM. No inline event handlers anywhere.
   =========================================================================== */

import { store } from './store.js';
import { t } from './i18n.js';

const routes = [];
let outlet = null;
let currentUnmount = null;

/**
 * @param {string} pattern  e.g. '/products/:id'
 * @param {object} view     { render, mount?, unmount?, title? }
 * @param {object} opts     { roles?: string[], public?: boolean }
 */
export function route(pattern, view, opts = {}) {
  const names = [];
  const rx = new RegExp(
    '^' + pattern.replace(/:([A-Za-z_]\w*)/g, (_, n) => { names.push(n); return '([^/]+)'; }) + '$',
  );
  routes.push({ pattern, rx, names, view, opts });
}

function match(path) {
  for (const r of routes) {
    const m = path.match(r.rx);
    if (m) {
      const params = {};
      r.names.forEach((n, i) => { params[n] = decodeURIComponent(m[i + 1]); });
      return { ...r, params };
    }
  }
  return null;
}

export function navigate(path, { replace = false } = {}) {
  const target = `#${path}`;
  if (replace) location.replace(target);
  else location.hash = target;
}

function currentPath() {
  return (location.hash || '#/').slice(1) || '/';
}

function skeleton() {
  return `<div class="skeleton-page" role="status" aria-live="polite">
    <span class="sr-only">${t('common.loading')}</span>
    <div class="skeleton skeleton--title"></div>
    <div class="skeleton skeleton--card"></div>
    <div class="skeleton skeleton--card"></div>
  </div>`;
}

function errorPage(err) {
  return `<div class="state state--error" role="alert">
    <h2 class="state__title">${t('common.error_title')}</h2>
    <p class="state__body">${err?.message || t('common.error_body')}</p>
    <button class="btn btn--primary" data-action="retry">${t('common.retry')}</button>
  </div>`;
}

async function resolve() {
  const path = currentPath();
  const hit = match(path);

  if (currentUnmount) { try { currentUnmount(); } catch { /* ignore */ } currentUnmount = null; }

  if (!hit) {
    outlet.innerHTML = `<div class="state state--empty">
      <h2 class="state__title">${t('common.not_found_title')}</h2>
      <a class="btn btn--primary" href="#/">${t('common.go_home')}</a>
    </div>`;
    return;
  }

  // --- auth gate ---------------------------------------------------------
  const session = store.get('session');
  if (!hit.opts.public && !session) {
    store.set('redirectAfterLogin', path);
    return navigate('/login', { replace: true });
  }
  if (hit.opts.roles?.length) {
    const role = store.get('profile')?.role;
    if (!role) return navigate('/login', { replace: true });
    if (!hit.opts.roles.includes(role)) {
      // Never a dead end: bounce to the caller's own dashboard.
      return navigate(`/${role}`, { replace: true });
    }
  }

  document.title = hit.view.title ? `${t(hit.view.title)} · UDGAM.ai` : 'UDGAM.ai';
  outlet.innerHTML = skeleton();

  try {
    outlet.innerHTML = await hit.view.render(hit.params);
    if (hit.view.mount) currentUnmount = await hit.view.mount(outlet, hit.params);
  } catch (err) {
    console.error('[router]', path, err);
    outlet.innerHTML = errorPage(err);
    outlet.querySelector('[data-action="retry"]')?.addEventListener('click', resolve);
  }
  window.scrollTo(0, 0);
}

export function startRouter(outletEl) {
  outlet = outletEl;
  window.addEventListener('hashchange', resolve);
  return resolve();
}

export const refresh = resolve;
