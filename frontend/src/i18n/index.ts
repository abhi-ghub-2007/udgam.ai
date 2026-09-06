/**
 * i18next setup. The three locale bundles are the SAME JSON files the legacy
 * app shipped -- copied, not rewritten, so all 426 existing keys keep working
 * and translators' work is preserved.
 *
 * keySeparator '.' matches the legacy t('market.orders_title') call shape, so
 * every existing key string ports over unchanged.
 */
import i18n from 'i18next';
import { initReactI18next } from 'react-i18next';
import en from './en.json';
import hi from './hi.json';
import mr from './mr.json';

export const LANGS = [
  { code: 'en', label: 'English' },
  { code: 'hi', label: 'हिन्दी' },
  { code: 'mr', label: 'मराठी' },
] as const;

const STORAGE_KEY = 'udgam.lang';

export function storedLang(): string {
  try {
    const v = localStorage.getItem(STORAGE_KEY);
    if (v && LANGS.some((l) => l.code === v)) return v;
  } catch { /* private mode */ }
  return 'en';
}

export function persistLang(code: string): void {
  try { localStorage.setItem(STORAGE_KEY, code); } catch { /* private mode */ }
  document.documentElement.lang = code;
}

void i18n.use(initReactI18next).init({
  resources: { en: { translation: en }, hi: { translation: hi }, mr: { translation: mr } },
  lng: storedLang(),
  fallbackLng: 'en',
  keySeparator: '.',
  nsSeparator: false,
  interpolation: {
    // React already escapes rendered values, so i18next must not double-escape.
    escapeValue: false,
    // The existing bundles use single-brace placeholders -- {name}, {n},
    // {price} -- inherited from the legacy renderer. i18next defaults to
    // {{name}}. Matching the data here is what keeps all 426 translated
    // strings working untouched; rewriting them to double braces would be a
    // pointless mass edit of translator output.
    prefix: '{',
    suffix: '}',
  },
  returnNull: false,
});

document.documentElement.lang = storedLang();

export default i18n;
