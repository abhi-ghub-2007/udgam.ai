/**
 * Public landing page.
 *
 * This is the first thing a judge sees, so it makes the core innovation
 * visible immediately rather than hiding it behind a login: the same lot sold
 * through different channels nets the farmer very different amounts, and UDGAM
 * does that arithmetic. The worked example below uses the real shape of a
 * Net Exit Optimizer result and is explicitly labelled as an example, not
 * presented as live data.
 */
import { Link } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { LANGS, persistLang } from '@/i18n';
import { money } from '@/utils/format';

const EXAMPLE = [
  { name: 'Direct buyer', net: 936_000, best: true },
  { name: 'Nashik mandi', net: 705_495, best: false },
  { name: 'Aurangabad mandi', net: 581_678, best: false },
  { name: 'Nagpur mandi', net: -252_617, best: false },
];

export default function Landing() {
  const { t, i18n } = useTranslation();
  const max = Math.max(...EXAMPLE.map((e) => Math.abs(e.net)));

  return (
    <div className="min-h-dvh bg-bg">
      <header className="border-b border-line-card bg-surface">
        <div className="mx-auto flex h-nav max-w-content items-center justify-between px-4">
          <span className="flex items-center gap-2 text-h2 font-bold text-ink">
            <img src="/assets/logo.svg" alt="" width={28} height={28} aria-hidden />
            UDGAM<span className="text-primary">.ai</span>
          </span>
          <div className="flex items-center gap-2">
            <label className="sr-only" htmlFor="lang-landing">{t('common.language')}</label>
            <select
              id="lang-landing" value={i18n.language}
              onChange={(e) => { void i18n.changeLanguage(e.target.value); persistLang(e.target.value); }}
              className="min-h-tap rounded-md border border-outline-variant bg-surface px-2 text-label"
            >
              {LANGS.map((l) => <option key={l.code} value={l.code}>{l.label}</option>)}
            </select>
            <Link to="/login"
                  className="inline-flex min-h-tap items-center rounded-md px-4 font-semibold text-primary hover:bg-primary-container/40">
              {t('auth.sign_in')}
            </Link>
          </div>
        </div>
      </header>

      <main id="main" className="mx-auto max-w-content px-4">
        {/* ------------------------------------------------------- hero --- */}
        <section className="grid items-center gap-10 py-14 lg:grid-cols-2 lg:py-20">
          <div className="space-y-6 animate-fade-up">
            <span className="inline-flex items-center rounded-full bg-primary-container px-3 py-1 text-label font-semibold text-primary-on-container">
              {t('landing.hero_badge')}
            </span>
            <h1 className="text-display font-bold leading-tight tracking-[-0.02em] text-ink lg:text-[2.75rem]">
              {t('landing.hero_title_1')} {t('landing.hero_title_2')}
            </h1>
            <p className="max-w-prose text-body text-ink-muted">{t('landing.hero_subtitle')}</p>
            <div className="flex flex-wrap gap-3">
              <Link to="/signup"
                    className="inline-flex min-h-tap-primary items-center rounded-md bg-primary px-6 font-semibold text-primary-on hover:bg-primary-strong">
                {t('landing.cta_get_started')}
              </Link>
              <Link to="/login"
                    className="inline-flex min-h-tap-primary items-center rounded-md border-card border-outline-variant bg-surface px-6 font-semibold text-ink hover:bg-surface-low">
                {t('auth.sign_in')}
              </Link>
            </div>
          </div>

          {/* The innovation, shown rather than described. */}
          <div className="rounded-lg border-card border-line-card bg-surface p-6 shadow-ambient animate-scale-in">
            <p className="text-label font-semibold uppercase tracking-[0.04em] text-ink-muted">
              {t('landing.transparency_eyebrow')}
            </p>
            <p className="mt-1 text-body text-ink-muted">{t('landing.transparency_sub')}</p>

            <ul className="mt-5 space-y-3">
              {EXAMPLE.map((e, i) => {
                const pct = Math.max(4, (Math.abs(e.net) / max) * 100);
                const negative = e.net < 0;
                return (
                  <li key={e.name} className="space-y-1 animate-fade-up"
                      style={{ animationDelay: `${i * 70}ms` }}>
                    <div className="flex items-baseline justify-between gap-3">
                      <span className={e.best ? 'font-semibold text-ink' : 'text-ink-muted'}>
                        {e.name}
                      </span>
                      <span className={`tnum font-bold ${negative ? 'text-danger' : e.best ? 'text-primary' : 'text-ink'}`}>
                        {money(e.net)}
                      </span>
                    </div>
                    <div className="h-2 overflow-hidden rounded-full bg-surface-high">
                      <div
                        className={`h-full origin-left rounded-full animate-draw-line ${
                          negative ? 'bg-danger' : e.best ? 'bg-primary' : 'bg-outline-variant'
                        }`}
                        style={{ width: `${pct}%`, animationDelay: `${i * 70}ms` }}
                      />
                    </div>
                  </li>
                );
              })}
            </ul>

            <p className="mt-5 rounded-md bg-surface-low px-3 py-2 text-label text-ink-muted">
              {t('landing.trans_sim_note')}
            </p>
          </div>
        </section>

        {/* --------------------------------------------------- for whom --- */}
        <section className="grid gap-4 pb-16 sm:grid-cols-3">
          {(['farmer', 'buyer', 'transporter'] as const).map((r) => (
            <div key={r} className="rounded-lg border-card border-line-card bg-surface p-5">
              <h2 className="text-h2 font-semibold text-ink">{t(`auth.role_${r}`)}</h2>
              <p className="mt-2 text-body text-ink-muted">{t(`landing.role_${r}_desc`)}</p>
            </div>
          ))}
        </section>
      </main>

      <footer className="border-t border-line-card bg-surface py-6">
        <p className="mx-auto max-w-content px-4 text-label text-ink-muted">
          {t('landing.footer_rights')}
        </p>
      </footer>
    </div>
  );
}
