/* ===========================================================================
   store.js - tiny pub/sub over a plain object (PRD section 5.1).
   The ONLY global mutable state in the app. Anything else lives inside a
   view's own mount() closure.
   =========================================================================== */

const state = {
  session: null,       // Supabase session
  profile: null,       // profiles row
  details: null,       // role detail row
  isFpo: false,
  lang: 'en',
  unreadCount: 0,
  online: navigator.onLine,
  stale: false,        // C-5: showing a cached payload
  redirectAfterLogin: null,
};

const subs = new Map();  // key -> Set<fn>

export const store = {
  get: (key) => state[key],
  all: () => ({ ...state }),

  set(key, value) {
    if (state[key] === value) return;
    state[key] = value;
    subs.get(key)?.forEach((fn) => fn(value));
  },

  patch(obj) {
    Object.entries(obj).forEach(([k, v]) => this.set(k, v));
  },

  /** Returns an unsubscribe function - call it from a view's unmount. */
  on(key, fn) {
    if (!subs.has(key)) subs.set(key, new Set());
    subs.get(key).add(fn);
    return () => subs.get(key)?.delete(fn);
  },
};

/* --- C-5: cache the last dashboard payload so a cold, offline load still
   renders something, with an honest stale banner above it. ---------------- */
const CACHE_PREFIX = 'udgam.cache.';

export const cache = {
  save(key, payload) {
    try {
      localStorage.setItem(
        CACHE_PREFIX + key, JSON.stringify({ at: Date.now(), payload }),
      );
    } catch { /* quota or private mode - caching is best-effort */ }
  },
  load(key) {
    try {
      const raw = localStorage.getItem(CACHE_PREFIX + key);
      return raw ? JSON.parse(raw) : null;
    } catch { return null; }
  },
  clear() {
    try {
      Object.keys(localStorage)
        .filter((k) => k.startsWith(CACHE_PREFIX))
        .forEach((k) => localStorage.removeItem(k));
    } catch { /* ignore */ }
  },
};

window.addEventListener('online',  () => store.set('online', true));
window.addEventListener('offline', () => store.set('online', false));
