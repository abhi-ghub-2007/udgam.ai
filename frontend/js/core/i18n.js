/* ===========================================================================
   i18n.js - C-2. English, Hindi, Marathi (A-19).

   A-20: t() exists before the first screen is written. No literal
   user-facing string is ever committed into markup, even while a translation
   is still missing - retrofitting i18n across thirty screens is the single
   most predictable way to lose a day.
   =========================================================================== */

import { store } from './store.js';

export const LANGS = [
  { code: 'en', label: 'English' },
  { code: 'hi', label: 'हिन्दी' },
  { code: 'mr', label: 'मराठी' },
];

const LS_KEY = 'udgam.lang';
const dicts = {};
let current = 'en';

function lookup(dict, key) {
  return key.split('.').reduce((o, k) => (o && typeof o === 'object' ? o[k] : undefined), dict);
}

/**
 * t('farmer.dashboard.title')
 * t('order.count', { n: 3 })  -> interpolates {n}
 * Falls back: current lang -> English -> the key itself (visible, so a
 * missing string is obvious in review rather than silently blank).
 */
export function t(key, params) {
  let s = lookup(dicts[current], key);
  if (s === undefined) s = lookup(dicts.en, key);
  if (s === undefined) {
    console.warn(`[i18n] missing key: ${key}`);
    return key;
  }
  if (params) {
    s = String(s).replace(/\{(\w+)\}/g, (m, k) => (k in params ? params[k] : m));
  }
  return s;
}

/** Rupee formatting happens here, once, from integer paise (A-6). */
export function money(paise, { compact = false } = {}) {
  const rupees = (paise || 0) / 100;
  return new Intl.NumberFormat(current === 'en' ? 'en-IN' : `${current}-IN`, {
    style: 'currency',
    currency: 'INR',
    maximumFractionDigits: rupees % 1 === 0 ? 0 : 2,
    notation: compact ? 'compact' : 'standard',
  }).format(rupees);
}

export function number(n) {
  return new Intl.NumberFormat(current === 'en' ? 'en-IN' : `${current}-IN`).format(n ?? 0);
}

export function date(iso, opts = { day: 'numeric', month: 'short', year: 'numeric' }) {
  if (!iso) return '';
  return new Intl.DateTimeFormat(current === 'en' ? 'en-IN' : `${current}-IN`, opts)
    .format(new Date(iso));
}

async function load(lang) {
  if (dicts[lang]) return;
  try {
    const res = await fetch(`./i18n/${lang}.json`);
    dicts[lang] = res.ok ? await res.json() : {};
  } catch {
    dicts[lang] = {};
  }
}

export async function setLang(lang) {
  if (!LANGS.some((l) => l.code === lang)) lang = 'en';
  await load(lang);
  current = lang;
  try { localStorage.setItem(LS_KEY, lang); } catch { /* ignore */ }
  document.documentElement.lang = lang;
  store.set('lang', lang);
}

export function getLang() {
  return current;
}

export async function initI18n() {
  await load('en');                       // always available as the fallback
  let saved = 'en';
  try { saved = localStorage.getItem(LS_KEY) || 'en'; } catch { /* ignore */ }
  await setLang(saved);
}

/** Re-translate every [data-i18n] node. Called on language switch so the
    whole UI flips without a reload (PRD section 13 step 9). */
export function applyTranslations(root = document) {
  root.querySelectorAll('[data-i18n]').forEach((el) => {
    el.textContent = t(el.dataset.i18n);
  });
  root.querySelectorAll('[data-i18n-attr]').forEach((el) => {
    // data-i18n-attr="aria-label:nav.home,title:nav.home_tip"
    el.dataset.i18nAttr.split(',').forEach((pair) => {
      const [attr, key] = pair.split(':');
      if (attr && key) el.setAttribute(attr.trim(), t(key.trim()));
    });
  });
}
