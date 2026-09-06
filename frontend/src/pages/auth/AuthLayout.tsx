import type { ReactNode } from 'react';
import { Link } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { LANGS, persistLang } from '@/i18n';

/** Shared chrome for the three public pages. */
export function AuthLayout({ title, subtitle, children, wide }: {
  title: string; subtitle?: string; children: ReactNode; wide?: boolean;
}) {
  const { t, i18n } = useTranslation();
  return (
    <div className="min-h-dvh bg-bg">
      <header className="border-b border-line-card bg-surface">
        <div className="mx-auto flex h-nav max-w-content items-center justify-between px-4">
          <Link to="/" className="flex items-center gap-2 font-bold text-ink">
            <img src="/assets/logo.svg" alt="" width={28} height={28} aria-hidden />
            <span className="text-h2">UDGAM<span className="text-primary">.ai</span></span>
          </Link>
          <label className="sr-only" htmlFor="lang-auth">{t('common.language')}</label>
          <select
            id="lang-auth"
            value={i18n.language}
            onChange={(e) => { void i18n.changeLanguage(e.target.value); persistLang(e.target.value); }}
            className="min-h-tap rounded-md border border-outline-variant bg-surface px-2 text-label"
          >
            {LANGS.map((l) => <option key={l.code} value={l.code}>{l.label}</option>)}
          </select>
        </div>
      </header>

      <main id="main" className="mx-auto w-full px-4 py-10" style={{ maxWidth: wide ? '48rem' : '28rem' }}>
        <div className="mb-6 space-y-1 text-center animate-fade-up">
          <h1 className="text-h1 font-bold tracking-[-0.02em] text-ink">{title}</h1>
          {subtitle && <p className="text-body text-ink-muted">{subtitle}</p>}
        </div>
        {children}
      </main>
    </div>
  );
}
