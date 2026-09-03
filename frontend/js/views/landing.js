/* ===========================================================================
   landing.js - Premium Front Door of UDGAM.ai (SIH 2026)
   Complete ecosystem presentation, AI intelligence showcase, tri-lingual
   localization, and seamless authentication routing to #/signup & #/login.
   =========================================================================== */

import { supabase } from '../core/supabase.js';
import { store } from '../core/store.js';
import { api } from '../core/api.js';
import { navigate, refresh } from '../core/router.js';
import { t, getLang, setLang, applyTranslations, LANGS } from '../core/i18n.js';
import { toast } from '../core/toast.js';

// Real demo accounts created by scripts/seed_demo.py for judge evaluation
const DEMO_PASSWORD = 'Udgam@1234';
const DEMO_EMAIL = {
  farmer: 'demo.farmer@udgam.test',
  buyer: 'demo.buyer@udgam.test',
  transporter: 'demo.transporter@udgam.test',
};

async function enterAs(role, btn) {
  const originalText = btn.innerHTML;
  btn.disabled = true;
  btn.textContent = t('common.loading');
  try {
    const { error } = await supabase.auth.signInWithPassword({
      email: DEMO_EMAIL[role],
      password: DEMO_PASSWORD,
    });
    if (error) throw new Error(error.message);

    const me = await api.get('/api/auth/me');
    const { data } = await supabase.auth.getSession();
    store.patch({
      session: data?.session || null,
      profile: me.profile,
      details: me.details,
      isFpo: me.is_fpo,
    });
    navigate(`/${role}`, { replace: true });
  } catch (ex) {
    toast(ex.message || t('common.error_body'), 'error');
    btn.disabled = false;
    btn.innerHTML = originalText;
  }
}

export function render() {
  const currentLang = getLang();

  return `
  <div class="landing-page">

    <!-- 1. Sticky Glassmorphic Navbar -->
    <header class="landing-nav" id="landing-navbar">
      <a class="landing-nav__brand" href="#/">
        <img class="landing-nav__logo" src="./assets/logo.svg" alt="UDGAM Logo" width="32" height="32">
        <span class="landing-nav__title">UDGAM<span class="landing-nav__dot">.ai</span></span>
      </a>

      <ul class="landing-nav__links">
        <li><a class="landing-nav__link" href="#problem">${t('landing.nav_how_it_works')}</a></li>
        <li><a class="landing-nav__link" href="#roles">${t('landing.nav_roles')}</a></li>
        <li><a class="landing-nav__link" href="#intelligence">${t('landing.nav_intelligence')}</a></li>
        <li><a class="landing-nav__link" href="#transparency">${t('landing.nav_transparency')}</a></li>
      </ul>

      <div class="landing-nav__actions">
        <div class="landing-nav__lang">
          <label for="landing-lang-select" class="sr-only">${t('common.language')}</label>
          <select id="landing-lang-select" class="landing-nav__lang-select" aria-label="${t('common.language')}">
            ${LANGS.map(l => `<option value="${l.code}" ${l.code === currentLang ? 'selected' : ''}>${l.label}</option>`).join('')}
          </select>
        </div>

        <a class="btn btn--ghost" href="#/login">${t('landing.nav_login')}</a>
        <a class="btn btn--primary" href="#/signup">${t('landing.nav_get_started')}</a>

        <button type="button" class="landing-nav__mobile-toggle" id="landing-mobile-toggle" aria-label="Toggle navigation menu" aria-expanded="false">
          <svg viewBox="0 0 24 24" width="24" height="24" aria-hidden="true" focusable="false">
            <path fill="currentColor" d="M3 18h18v-2H3v2zm0-5h18v-2H3v2zm0-7v2h18V6H3z"/>
          </svg>
        </button>
      </div>
    </header>

    <!-- Mobile Dropdown Menu -->
    <div class="landing-mobile-menu" id="landing-mobile-menu" hidden>
      <a class="landing-nav__link" href="#problem">${t('landing.nav_how_it_works')}</a>
      <a class="landing-nav__link" href="#roles">${t('landing.nav_roles')}</a>
      <a class="landing-nav__link" href="#intelligence">${t('landing.nav_intelligence')}</a>
      <a class="landing-nav__link" href="#transparency">${t('landing.nav_transparency')}</a>
      <hr style="border:0;border-top:1px solid var(--c-border-card);margin:4px 0;">
      <a class="btn btn--outline btn--block" href="#/login">${t('landing.nav_login')}</a>
      <a class="btn btn--primary btn--block" href="#/signup">${t('landing.nav_get_started')}</a>
    </div>

    <!-- 2. Hero Section -->
    <section class="landing-hero" id="hero">
      <div class="landing-hero__content">
        <div class="landing-badge">
          <span class="landing-badge__dot"></span>
          <span>${t('landing.hero_badge')}</span>
        </div>

        <h1 class="landing-hero__headline">
          ${t('landing.hero_title_1')}<br>
          <span>${t('landing.hero_title_2')}</span>
        </h1>

        <p class="landing-hero__sub">
          ${t('landing.hero_subtitle')}
        </p>

        <div class="landing-hero__ctas">
          <a class="btn btn--primary landing-hero__btn-main" href="#/signup">
            <span>${t('landing.cta_get_started')}</span>
            <svg viewBox="0 0 24 24" width="20" height="20" aria-hidden="true" focusable="false">
              <path fill="currentColor" d="M12 4l-1.41 1.41L16.17 11H4v2h12.17l-5.58 5.59L12 20l8-8z"/>
            </svg>
          </a>
          <a class="btn btn--outline landing-hero__btn-main" href="#roles">
            <span>${t('landing.cta_explore')}</span>
          </a>
        </div>
      </div>

      <!-- Hero Visual: Real-time Ecosystem Journey -->
      <div class="landing-hero__visual-container">
        <div class="landing-visual-backdrop"></div>
        <div class="landing-visual-stack">
          <div class="landing-visual-header">
            <span class="landing-visual-title">
              <svg viewBox="0 0 24 24" width="16" height="16" aria-hidden="true">
                <path fill="currentColor" d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm-1 14h2v2h-2zm0-10h2v8h-2z"/>
              </svg>
              Live Agricultural Flow
            </span>
            <span class="landing-visual-live">
              <span style="width:6px;height:6px;border-radius:50%;background:var(--c-primary);display:inline-block"></span>
              Synchronized
            </span>
          </div>

          <div class="landing-flow">
            <!-- Node 1: Producer -->
            <div class="landing-flow-node">
              <div class="landing-flow-icon landing-flow-icon--green">
                <svg viewBox="0 0 24 24" width="24" height="24" fill="currentColor">
                  <path d="M12 3 2 12h3v8h6v-6h2v6h6v-8h3Z"/>
                </svg>
              </div>
              <div class="landing-flow-info">
                <span class="landing-flow-name">${t('landing.hero_card_produce')}</span>
                <span class="landing-flow-detail">${t('landing.hero_card_produce_loc')} · ${t('landing.hero_card_qty')}</span>
              </div>
              <div class="landing-flow-badge">
                <span class="badge badge--grade-a">${t('landing.hero_card_grade_a')}</span>
                <span style="font-size:11px;color:var(--c-ink-muted)">${t('landing.hero_card_confidence')}</span>
              </div>
            </div>

            <div class="landing-flow-connector">
              <svg viewBox="0 0 24 24" width="16" height="16" fill="currentColor"><path d="M7.41 8.59L12 13.17l4.59-4.58L18 10l-6 6-6-6 1.41-1.41z"/></svg>
            </div>

            <!-- Node 2: AI Matching -->
            <div class="landing-flow-node">
              <div class="landing-flow-icon landing-flow-icon--purple">
                <svg viewBox="0 0 24 24" width="24" height="24" fill="currentColor">
                  <path d="M12 2a10 10 0 1 0 10 10A10 10 0 0 0 12 2zm1 15h-2v-6h2zm0-8h-2V7h2z"/>
                </svg>
              </div>
              <div class="landing-flow-info">
                <span class="landing-flow-name">${t('landing.hero_card_matched')}</span>
                <span class="landing-flow-detail">Verified FMCG Procurement Entity</span>
              </div>
              <div class="landing-flow-badge">
                <span class="badge badge--info" style="background:#ede7f6;color:var(--c-insight)">${t('landing.hero_card_match_score')}</span>
                <span style="font-size:11px;color:var(--c-ink-muted)">Grade A Matched</span>
              </div>
            </div>

            <div class="landing-flow-connector">
              <svg viewBox="0 0 24 24" width="16" height="16" fill="currentColor"><path d="M7.41 8.59L12 13.17l4.59-4.58L18 10l-6 6-6-6 1.41-1.41z"/></svg>
            </div>

            <!-- Node 3: Logistics Route -->
            <div class="landing-flow-node">
              <div class="landing-flow-icon landing-flow-icon--gold">
                <svg viewBox="0 0 24 24" width="24" height="24" fill="currentColor">
                  <path d="M3 7h11v8H3Zm11 3h4l3 3v2h-7Zm-7 8a2 2 0 1 0 0-4 2 2 0 0 0 0 4Zm11 0a2 2 0 1 0 0-4 2 2 0 0 0 0 4Z"/>
                </svg>
              </div>
              <div class="landing-flow-info">
                <span class="landing-flow-name">${t('landing.hero_card_route')}</span>
                <span class="landing-flow-detail">Farm Gate → Direct Mumbai Warehouse</span>
              </div>
              <div class="landing-flow-badge">
                <span class="badge badge--warning">${t('landing.hero_card_route_saving')}</span>
                <span style="font-size:11px;color:var(--c-ink-muted)">Consolidated</span>
              </div>
            </div>

            <div class="landing-flow-connector">
              <svg viewBox="0 0 24 24" width="16" height="16" fill="currentColor"><path d="M7.41 8.59L12 13.17l4.59-4.58L18 10l-6 6-6-6 1.41-1.41z"/></svg>
            </div>

            <!-- Node 4: Realization -->
            <div class="landing-flow-node" style="background:var(--c-primary-container);border-color:var(--c-primary)">
              <div class="landing-flow-icon" style="background:var(--c-primary);color:var(--c-on-primary)">
                <svg viewBox="0 0 24 24" width="24" height="24" fill="currentColor">
                  <path d="M9 16.17L4.83 12l-1.42 1.41L9 19 21 7l-1.41-1.41z"/>
                </svg>
              </div>
              <div class="landing-flow-info">
                <span class="landing-flow-name" style="color:var(--c-on-primary-container)">${t('landing.hero_card_payout')}</span>
                <span class="landing-flow-detail" style="color:var(--c-on-primary-container)">${t('landing.hero_card_settled')}</span>
              </div>
              <div class="landing-flow-badge">
                <b style="font-size:var(--fs-h2);color:var(--c-primary-strong)">${t('landing.hero_card_amount')}</b>
                <span style="font-size:11px;color:var(--c-primary-strong);font-weight:600">Zero Commission</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </section>

    <!-- 3. Key Metrics Ribbon -->
    <section class="landing-section" style="padding-top:0">
      <div class="landing-stats-grid">
        <div class="landing-stat-card">
          <span class="landing-stat-num">${t('landing.stat_farmer_share_val')}</span>
          <span class="landing-stat-lbl">${t('landing.stat_farmer_share')}</span>
        </div>
        <div class="landing-stat-card">
          <span class="landing-stat-num">${t('landing.stat_intermediaries_val')}</span>
          <span class="landing-stat-lbl">${t('landing.stat_intermediaries')}</span>
        </div>
        <div class="landing-stat-card">
          <span class="landing-stat-num">${t('landing.stat_route_saving_val')}</span>
          <span class="landing-stat-lbl">${t('landing.stat_route_saving')}</span>
        </div>
        <div class="landing-stat-card">
          <span class="landing-stat-num">${t('landing.stat_settlement_val')}</span>
          <span class="landing-stat-lbl">${t('landing.stat_settlement')}</span>
        </div>
      </div>
    </section>

    <!-- 4. Section: Problem vs UDGAM Protocol -->
    <section class="landing-section" id="problem">
      <div class="landing-section-head">
        <span class="landing-eyebrow">${t('landing.problem_eyebrow')}</span>
        <h2 class="landing-section-title">${t('landing.problem_title')}</h2>
        <p class="landing-section-sub">${t('landing.problem_sub')}</p>
      </div>

      <div class="landing-problem-grid">
        <!-- Traditional Supply Chain -->
        <div class="landing-comp-card landing-comp-card--trad">
          <div class="landing-comp-head">
            <span style="display:flex;align-items:center;justify-content:center;width:32px;height:32px;border-radius:50%;background:#ffcdd2;color:#b71c1c">✕</span>
            <h3 class="landing-comp-title">${t('landing.problem_trad_title')}</h3>
          </div>
          <ul class="landing-comp-list">
            <li class="landing-comp-item">
              <svg viewBox="0 0 24 24" width="18" height="18" fill="#d32f2f"><path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm1 15h-2v-2h2zm0-4h-2V7h2z"/></svg>
              <span>${t('landing.problem_trad_1')}</span>
            </li>
            <li class="landing-comp-item">
              <svg viewBox="0 0 24 24" width="18" height="18" fill="#d32f2f"><path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm1 15h-2v-2h2zm0-4h-2V7h2z"/></svg>
              <span>${t('landing.problem_trad_2')}</span>
            </li>
            <li class="landing-comp-item">
              <svg viewBox="0 0 24 24" width="18" height="18" fill="#d32f2f"><path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm1 15h-2v-2h2zm0-4h-2V7h2z"/></svg>
              <span>${t('landing.problem_trad_3')}</span>
            </li>
            <li class="landing-comp-item">
              <svg viewBox="0 0 24 24" width="18" height="18" fill="#d32f2f"><path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm1 15h-2v-2h2zm0-4h-2V7h2z"/></svg>
              <span>${t('landing.problem_trad_4')}</span>
            </li>
          </ul>
        </div>

        <!-- UDGAM Connected Protocol -->
        <div class="landing-comp-card landing-comp-card--udgam">
          <div class="landing-comp-head">
            <span style="display:flex;align-items:center;justify-content:center;width:32px;height:32px;border-radius:50%;background:var(--c-primary-container);color:var(--c-primary-strong)">✓</span>
            <h3 class="landing-comp-title">${t('landing.problem_udgam_title')}</h3>
          </div>
          <ul class="landing-comp-list">
            <li class="landing-comp-item">
              <svg viewBox="0 0 24 24" width="18" height="18" fill="var(--c-primary)"><path d="M9 16.17L4.83 12l-1.42 1.41L9 19 21 7l-1.41-1.41z"/></svg>
              <span><b>${t('landing.problem_udgam_1')}</b></span>
            </li>
            <li class="landing-comp-item">
              <svg viewBox="0 0 24 24" width="18" height="18" fill="var(--c-primary)"><path d="M9 16.17L4.83 12l-1.42 1.41L9 19 21 7l-1.41-1.41z"/></svg>
              <span><b>${t('landing.problem_udgam_2')}</b></span>
            </li>
            <li class="landing-comp-item">
              <svg viewBox="0 0 24 24" width="18" height="18" fill="var(--c-primary)"><path d="M9 16.17L4.83 12l-1.42 1.41L9 19 21 7l-1.41-1.41z"/></svg>
              <span><b>${t('landing.problem_udgam_3')}</b></span>
            </li>
            <li class="landing-comp-item">
              <svg viewBox="0 0 24 24" width="18" height="18" fill="var(--c-primary)"><path d="M9 16.17L4.83 12l-1.42 1.41L9 19 21 7l-1.41-1.41z"/></svg>
              <span><b>${t('landing.problem_udgam_4')}</b></span>
            </li>
          </ul>
        </div>
      </div>
    </section>

    <!-- 5. Section: Ecosystem Roles (Interactive 3 Pillars) -->
    <section class="landing-section" id="roles">
      <div class="landing-section-head">
        <span class="landing-eyebrow">${t('landing.roles_eyebrow')}</span>
        <h2 class="landing-section-title">${t('landing.roles_title')}</h2>
        <p class="landing-section-sub">${t('landing.roles_sub')}</p>
      </div>

      <div class="landing-roles-container">
        <!-- Role Nav Switcher -->
        <div class="landing-role-nav" role="tablist" id="landing-role-tabs">
          <button type="button" class="landing-role-tab" role="tab" aria-selected="true" data-tab="farmer">
            🌾 ${t('landing.role_tab_farmer')}
          </button>
          <button type="button" class="landing-role-tab" role="tab" aria-selected="false" data-tab="buyer">
            🛒 ${t('landing.role_tab_buyer')}
          </button>
          <button type="button" class="landing-role-tab" role="tab" aria-selected="false" data-tab="transporter">
            🚛 ${t('landing.role_tab_transporter')}
          </button>
        </div>

        <!-- Role Card 1: Farmer -->
        <div class="landing-role-card" id="role-panel-farmer">
          <div class="landing-role-info">
            <h3 class="landing-role-title">${t('landing.role_farmer_title')}</h3>
            <p class="landing-role-desc">${t('landing.role_farmer_desc')}</p>
            <div class="landing-role-features">
              <div class="landing-role-feat-item">
                <svg viewBox="0 0 24 24" width="18" height="18" fill="currentColor"><path d="M9 16.17L4.83 12l-1.42 1.41L9 19 21 7l-1.41-1.41z"/></svg>
                <span>${t('landing.role_farmer_f1')}</span>
              </div>
              <div class="landing-role-feat-item">
                <svg viewBox="0 0 24 24" width="18" height="18" fill="currentColor"><path d="M9 16.17L4.83 12l-1.42 1.41L9 19 21 7l-1.41-1.41z"/></svg>
                <span>${t('landing.role_farmer_f2')}</span>
              </div>
              <div class="landing-role-feat-item">
                <svg viewBox="0 0 24 24" width="18" height="18" fill="currentColor"><path d="M9 16.17L4.83 12l-1.42 1.41L9 19 21 7l-1.41-1.41z"/></svg>
                <span>${t('landing.role_farmer_f3')}</span>
              </div>
              <div class="landing-role-feat-item">
                <svg viewBox="0 0 24 24" width="18" height="18" fill="currentColor"><path d="M9 16.17L4.83 12l-1.42 1.41L9 19 21 7l-1.41-1.41z"/></svg>
                <span>${t('landing.role_farmer_f4')}</span>
              </div>
            </div>
            <div>
              <a class="btn btn--primary" href="#/signup">${t('landing.nav_get_started')} (${t('landing.role_tab_farmer')})</a>
            </div>
          </div>
          <div class="landing-role-preview-box">
            <span style="font-size:12px;font-weight:700;letter-spacing:var(--ls-caps);color:var(--c-primary);text-transform:uppercase">Farmer Experience Preview</span>
            <div style="display:flex;justify-content:space-between;align-items:center;padding:8px 12px;background:var(--c-surface);border-radius:var(--r-md);border:1px solid var(--c-border-card)">
              <div><b>Sharbati Wheat (Grade A)</b><br><small style="color:var(--c-ink-muted)">2,500 kg · Asking ₹34/kg</small></div>
              <span class="badge badge--success">Active Lot</span>
            </div>
            <div style="display:flex;justify-content:space-between;align-items:center;padding:8px 12px;background:var(--c-surface);border-radius:var(--r-md);border:1px solid var(--c-border-card)">
              <div><b>Agri-Flour Mills Offer</b><br><small style="color:var(--c-ink-muted)">₹34/kg · Full lot demand</small></div>
              <span class="badge badge--info">98% Match</span>
            </div>
          </div>
        </div>

        <!-- Role Card 2: Buyer (Hidden by default, toggled via JS) -->
        <div class="landing-role-card" id="role-panel-buyer" hidden>
          <div class="landing-role-info">
            <h3 class="landing-role-title">${t('landing.role_buyer_title')}</h3>
            <p class="landing-role-desc">${t('landing.role_buyer_desc')}</p>
            <div class="landing-role-features">
              <div class="landing-role-feat-item">
                <svg viewBox="0 0 24 24" width="18" height="18" fill="currentColor"><path d="M9 16.17L4.83 12l-1.42 1.41L9 19 21 7l-1.41-1.41z"/></svg>
                <span>${t('landing.role_buyer_f1')}</span>
              </div>
              <div class="landing-role-feat-item">
                <svg viewBox="0 0 24 24" width="18" height="18" fill="currentColor"><path d="M9 16.17L4.83 12l-1.42 1.41L9 19 21 7l-1.41-1.41z"/></svg>
                <span>${t('landing.role_buyer_f2')}</span>
              </div>
              <div class="landing-role-feat-item">
                <svg viewBox="0 0 24 24" width="18" height="18" fill="currentColor"><path d="M9 16.17L4.83 12l-1.42 1.41L9 19 21 7l-1.41-1.41z"/></svg>
                <span>${t('landing.role_buyer_f3')}</span>
              </div>
              <div class="landing-role-feat-item">
                <svg viewBox="0 0 24 24" width="18" height="18" fill="currentColor"><path d="M9 16.17L4.83 12l-1.42 1.41L9 19 21 7l-1.41-1.41z"/></svg>
                <span>${t('landing.role_buyer_f4')}</span>
              </div>
            </div>
            <div>
              <a class="btn btn--primary" href="#/signup">${t('landing.nav_get_started')} (${t('landing.role_tab_buyer')})</a>
            </div>
          </div>
          <div class="landing-role-preview-box">
            <span style="font-size:12px;font-weight:700;letter-spacing:var(--ls-caps);color:var(--c-primary);text-transform:uppercase">Buyer Sourcing Preview</span>
            <div style="display:flex;justify-content:space-between;align-items:center;padding:8px 12px;background:var(--c-surface);border-radius:var(--r-md);border:1px solid var(--c-border-card)">
              <div><b>Red Onion (Grade A)</b><br><small style="color:var(--c-ink-muted)">Nashik FPO · 5,000 kg</small></div>
              <span class="badge badge--grade-a">CV Verified</span>
            </div>
            <div style="display:flex;justify-content:space-between;align-items:center;padding:8px 12px;background:var(--c-surface);border-radius:var(--r-md);border:1px solid var(--c-border-card)">
              <div><b>Milestone: In Transit</b><br><small style="color:var(--c-ink-muted)">Truck MH-15-AB-4021 · OTP Secured</small></div>
              <span class="badge badge--warning">Live GPS</span>
            </div>
          </div>
        </div>

        <!-- Role Card 3: Transporter (Hidden by default, toggled via JS) -->
        <div class="landing-role-card" id="role-panel-transporter" hidden>
          <div class="landing-role-info">
            <h3 class="landing-role-title">${t('landing.role_transporter_title')}</h3>
            <p class="landing-role-desc">${t('landing.role_transporter_desc')}</p>
            <div class="landing-role-features">
              <div class="landing-role-feat-item">
                <svg viewBox="0 0 24 24" width="18" height="18" fill="currentColor"><path d="M9 16.17L4.83 12l-1.42 1.41L9 19 21 7l-1.41-1.41z"/></svg>
                <span>${t('landing.role_transporter_f1')}</span>
              </div>
              <div class="landing-role-feat-item">
                <svg viewBox="0 0 24 24" width="18" height="18" fill="currentColor"><path d="M9 16.17L4.83 12l-1.42 1.41L9 19 21 7l-1.41-1.41z"/></svg>
                <span>${t('landing.role_transporter_f2')}</span>
              </div>
              <div class="landing-role-feat-item">
                <svg viewBox="0 0 24 24" width="18" height="18" fill="currentColor"><path d="M9 16.17L4.83 12l-1.42 1.41L9 19 21 7l-1.41-1.41z"/></svg>
                <span>${t('landing.role_transporter_f3')}</span>
              </div>
              <div class="landing-role-feat-item">
                <svg viewBox="0 0 24 24" width="18" height="18" fill="currentColor"><path d="M9 16.17L4.83 12l-1.42 1.41L9 19 21 7l-1.41-1.41z"/></svg>
                <span>${t('landing.role_transporter_f4')}</span>
              </div>
            </div>
            <div>
              <a class="btn btn--primary" href="#/signup">${t('landing.nav_get_started')} (${t('landing.role_tab_transporter')})</a>
            </div>
          </div>
          <div class="landing-role-preview-box">
            <span style="font-size:12px;font-weight:700;letter-spacing:var(--ls-caps);color:var(--c-primary);text-transform:uppercase">Fleet Utilization Preview</span>
            <div style="display:flex;justify-content:space-between;align-items:center;padding:8px 12px;background:var(--c-surface);border-radius:var(--r-md);border:1px solid var(--c-border-card)">
              <div><b>Consolidated Agri Route</b><br><small style="color:var(--c-ink-muted)">3 Farm Pickups → Pune Mandi (78 km)</small></div>
              <span class="badge badge--success">92% Capacity</span>
            </div>
            <div style="display:flex;justify-content:space-between;align-items:center;padding:8px 12px;background:var(--c-surface);border-radius:var(--r-md);border:1px solid var(--c-border-card)">
              <div><b>Guaranteed Freight Payout</b><br><small style="color:var(--c-ink-muted)">Auto-release via Delivery OTP</small></div>
              <b style="color:var(--c-primary)">₹5,800</b>
            </div>
          </div>
        </div>
      </div>
    </section>

    <!-- 6. Section: AI & Intelligence Layer -->
    <section class="landing-section" id="intelligence">
      <div class="landing-section-head">
        <span class="landing-eyebrow landing-eyebrow--insight">${t('landing.ai_eyebrow')}</span>
        <h2 class="landing-section-title">${t('landing.ai_title')}</h2>
        <p class="landing-section-sub">${t('landing.ai_sub')}</p>
      </div>

      <div class="landing-ai-grid">
        <!-- AI Card 1: Quality Grading -->
        <div class="landing-ai-card">
          <span class="landing-ai-tag">${t('landing.ai_card1_tag')}</span>
          <h3 class="landing-ai-card-title">${t('landing.ai_card1_title')}</h3>
          <p class="landing-ai-card-desc">${t('landing.ai_card1_desc')}</p>
          <div style="margin-top:auto;display:flex;gap:6px;flex-wrap:wrap">
            <span class="badge badge--method">Honest AI Output</span>
            <span class="badge badge--grade-a">Grade A / B / C</span>
          </div>
        </div>

        <!-- AI Card 2: Matching Engine -->
        <div class="landing-ai-card">
          <span class="landing-ai-tag">${t('landing.ai_card2_tag')}</span>
          <h3 class="landing-ai-card-title">${t('landing.ai_card2_title')}</h3>
          <p class="landing-ai-card-desc">${t('landing.ai_card2_desc')}</p>
          <div style="margin-top:auto;display:flex;gap:6px;flex-wrap:wrap">
            <span class="badge badge--info">Multi-Variable Score</span>
            <span class="badge badge--success">Distance Aware</span>
          </div>
        </div>

        <!-- AI Card 3: Route Optimization -->
        <div class="landing-ai-card">
          <span class="landing-ai-tag">${t('landing.ai_card3_tag')}</span>
          <h3 class="landing-ai-card-title">${t('landing.ai_card3_title')}</h3>
          <p class="landing-ai-card-desc">${t('landing.ai_card3_desc')}</p>
          <div style="margin-top:auto;display:flex;gap:6px;flex-wrap:wrap">
            <span class="badge badge--warning">Load Pooling</span>
            <span class="badge badge--method">Waypoint TSP</span>
          </div>
        </div>

        <!-- AI Card 4: Market Signals -->
        <div class="landing-ai-card">
          <span class="landing-ai-tag">${t('landing.ai_card4_tag')}</span>
          <h3 class="landing-ai-card-title">${t('landing.ai_card4_title')}</h3>
          <p class="landing-ai-card-desc">${t('landing.ai_card4_desc')}</p>
          <div style="margin-top:auto;display:flex;gap:6px;flex-wrap:wrap">
            <span class="badge badge--grade-b">APMC Mandi Benchmarks</span>
            <span class="badge badge--info">Trend Analysis</span>
          </div>
        </div>
      </div>
    </section>

    <!-- 7. Section: Financial Transparency & Integrity -->
    <section class="landing-section" id="transparency">
      <div class="landing-section-head">
        <span class="landing-eyebrow">${t('landing.transparency_eyebrow')}</span>
        <h2 class="landing-section-title">${t('landing.transparency_title')}</h2>
        <p class="landing-section-sub">${t('landing.transparency_sub')}</p>
      </div>

      <div class="landing-transparency-card">
        <h3 style="font-size:var(--fs-h2);margin:0;color:var(--c-ink)">${t('landing.trans_sim_title')}</h3>
        
        <div class="landing-trans-row">
          <span>${t('landing.trans_sim_item')}</span>
          <b style="color:var(--c-primary-strong)">${t('landing.trans_sim_item_val')}</b>
        </div>

        <div class="landing-trans-row">
          <span>${t('landing.trans_sim_trans')}</span>
          <b>${t('landing.trans_sim_trans_val')}</b>
        </div>

        <div class="landing-trans-row">
          <span>${t('landing.trans_sim_fee')}</span>
          <span style="color:var(--c-ink-muted)">${t('landing.trans_sim_fee_val')}</span>
        </div>

        <div class="landing-trans-row landing-trans-row--total">
          <span>${t('landing.trans_sim_total')}</span>
          <span>${t('landing.trans_sim_total_val')}</span>
        </div>

        <div class="landing-trans-note">
          <svg viewBox="0 0 24 24" width="20" height="20" fill="var(--c-primary)"><path d="M12 1L3 5v6c0 5.55 3.84 10.74 9 12 5.16-1.26 9-6.45 9-12V5l-9-4zm-2 16l-4-4 1.41-1.41L10 14.17l6.59-6.59L18 9l-8 8z"/></svg>
          <span>${t('landing.trans_sim_note')}</span>
        </div>
      </div>
    </section>

    <!-- 8. Section: Trust & Built for Bharat -->
    <section class="landing-section" id="trust">
      <div class="landing-section-head">
        <span class="landing-eyebrow">${t('landing.trust_eyebrow')}</span>
        <h2 class="landing-section-title">${t('landing.trust_title')}</h2>
      </div>

      <div class="landing-trust-grid">
        <div class="landing-trust-card">
          <div class="landing-trust-icon">
            <svg viewBox="0 0 24 24" width="24" height="24" fill="currentColor"><path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm-1 17.93c-3.95-.49-7-3.85-7-7.93 0-.62.08-1.21.21-1.79L9 15v1c0 1.1.9 2 2 2v1.93zm6.9-2.54c-.26-.81-1-1.39-1.9-1.39h-1v-3c0-.55-.45-1-1-1H8v-2h2c.55 0 1-.45 1-1V7h2c1.1 0 2-.9 2-2v-.41c2.93 1.19 5 4.06 5 7.41 0 2.08-.8 3.97-2.1 5.39z"/></svg>
          </div>
          <h3 class="landing-trust-title">${t('landing.trust_f1_title')}</h3>
          <p class="landing-trust-desc">${t('landing.trust_f1_desc')}</p>
        </div>

        <div class="landing-trust-card">
          <div class="landing-trust-icon">
            <svg viewBox="0 0 24 24" width="24" height="24" fill="currentColor"><path d="M1 9l2 2c4.97-4.97 13.03-4.97 18 0l2-2C16.93 2.93 7.08 2.93 1 9zm8 8l3 3 3-3c-1.65-1.66-4.34-1.66-6 0zm-4-4l2 2c2.76-2.76 7.24-2.76 10 0l2-2C15.14 9.14 8.87 9.14 5 13z"/></svg>
          </div>
          <h3 class="landing-trust-title">${t('landing.trust_f2_title')}</h3>
          <p class="landing-trust-desc">${t('landing.trust_f2_desc')}</p>
        </div>

        <div class="landing-trust-card">
          <div class="landing-trust-icon">
            <svg viewBox="0 0 24 24" width="24" height="24" fill="currentColor"><path d="M9 11.24V7.5C9 6.12 10.12 5 11.5 5S14 6.12 14 7.5v3.74c1.21-.81 2-2.18 2-3.74C16 5.01 13.99 3 11.5 3S7 5.01 7 7.5c0 1.56.79 2.93 2 3.74zM18.84 15.25l-4.28-2.14c-.33-.16-.71-.22-1.09-.16l-1.97.33V7.5c0-.28-.22-.5-.5-.5s-.5.22-.5.5v10.61l-3.33-.7c-.36-.08-.74.03-1 .29l-.67.63 4.54 4.54c.47.47 1.1.73 1.76.73h6.42c1.07 0 1.97-.79 2.09-1.85l.59-5.18c.07-.63-.2-1.25-.7-1.5-.02 0-.04-.01-.06-.02z"/></svg>
          </div>
          <h3 class="landing-trust-title">${t('landing.trust_f3_title')}</h3>
          <p class="landing-trust-desc">${t('landing.trust_f3_desc')}</p>
        </div>

        <div class="landing-trust-card">
          <div class="landing-trust-icon">
            <svg viewBox="0 0 24 24" width="24" height="24" fill="currentColor"><path d="M18 8h-1V6c0-2.76-2.24-5-5-5S7 3.24 7 6v2H6c-1.1 0-2 .9-2 2v10c0 1.1.9 2 2 2h12c1.1 0 2-.9 2-2V10c0-1.1-.9-2-2-2zm-6 9c-1.1 0-2-.9-2-2s.9-2 2-2 2 .9 2 2-.9 2-2 2zm3.1-9H8.9V6c0-1.71 1.39-3.1 3.1-3.1 1.71 0 3.1 1.39 3.1 3.1v2z"/></svg>
          </div>
          <h3 class="landing-trust-title">${t('landing.trust_f4_title')}</h3>
          <p class="landing-trust-desc">${t('landing.trust_f4_desc')}</p>
        </div>
      </div>
    </section>

    <!-- 9. Final Call To Action Banner -->
    <section class="landing-section" style="padding-bottom:0">
      <div class="landing-cta-banner">
        <h2 class="landing-cta-banner__title">${t('landing.cta_banner_title')}</h2>
        <p class="landing-cta-banner__sub">${t('landing.cta_banner_sub')}</p>
        <div class="landing-cta-banner__actions">
          <a class="btn landing-cta-banner__btn-white" href="#/signup">${t('landing.cta_get_started')}</a>
          <a class="btn btn--outline landing-cta-banner__btn-ghost" href="#/login">${t('landing.nav_login')}</a>
        </div>
      </div>
    </section>

    <!-- 10. Enterprise Footer -->
    <footer class="landing-footer">
      <div class="landing-footer__inner">
        <div class="landing-footer__brand">
          <div style="display:flex;align-items:center;gap:8px">
            <img src="./assets/logo.svg" alt="" width="28" height="28">
            <span class="landing-footer__name">UDGAM<span style="color:var(--c-primary)">.ai</span></span>
          </div>
          <p class="landing-footer__desc">${t('landing.footer_brand_desc')}</p>
          <small style="color:var(--c-ink-muted)">${t('landing.footer_sih')}</small>
        </div>

        <div class="landing-footer__col">
          <span class="landing-footer__col-title">${t('landing.footer_links_platform')}</span>
          <ul class="landing-footer__links">
            <li><a class="landing-footer__link" href="#problem">${t('landing.nav_how_it_works')}</a></li>
            <li><a class="landing-footer__link" href="#intelligence">${t('landing.nav_intelligence')}</a></li>
            <li><a class="landing-footer__link" href="#transparency">${t('landing.nav_transparency')}</a></li>
          </ul>
        </div>

        <div class="landing-footer__col">
          <span class="landing-footer__col-title">${t('landing.footer_links_roles')}</span>
          <ul class="landing-footer__links">
            <li><a class="landing-footer__link" href="#/signup">${t('auth.role_farmer')}</a></li>
            <li><a class="landing-footer__link" href="#/signup">${t('auth.role_buyer')}</a></li>
            <li><a class="landing-footer__link" href="#/signup">${t('auth.role_transporter')}</a></li>
            <li><a class="landing-footer__link" href="#/login">${t('auth.sign_in')}</a></li>
          </ul>
        </div>
      </div>

      <div class="landing-footer__bottom">
        <span>© 2026 UDGAM.ai · ${t('landing.footer_rights')}</span>
        <span>SIH 2026 Problem Statement SIH26033</span>
      </div>
    </footer>

  </div>`;
}

export function mount(root) {
  // 1. Language switcher inside landing navbar
  const langSelect = root.querySelector('#landing-lang-select');
  if (langSelect) {
    langSelect.addEventListener('change', async (e) => {
      await setLang(e.target.value);
      applyTranslations();
      refresh();
    });
  }

  // 2. Mobile menu toggle
  const mobileToggle = root.querySelector('#landing-mobile-toggle');
  const mobileMenu = root.querySelector('#landing-mobile-menu');
  if (mobileToggle && mobileMenu) {
    mobileToggle.addEventListener('click', () => {
      const isHidden = mobileMenu.hidden;
      mobileMenu.hidden = !isHidden;
      mobileToggle.setAttribute('aria-expanded', String(isHidden));
    });

    mobileMenu.addEventListener('click', (e) => {
      if (e.target.closest('a')) {
        mobileMenu.hidden = true;
        mobileToggle.setAttribute('aria-expanded', 'false');
      }
    });
  }

  // 3. Smooth scrolling for internal anchors
  const onAnchorClick = (e) => {
    const link = e.target.closest('a[href^="#"]');
    if (!link) return;
    const targetId = link.getAttribute('href').slice(1);
    if (targetId.startsWith('/')) return; // Allow router links like #/login, #/signup
    const targetEl = root.querySelector(`#${targetId}`);
    if (targetEl) {
      e.preventDefault();
      targetEl.scrollIntoView({ behavior: 'smooth' });
    }
  };
  root.addEventListener('click', onAnchorClick);

  // 4. Role tabs switcher (Farmer / Buyer / Transporter)
  const tabsContainer = root.querySelector('#landing-role-tabs');
  if (tabsContainer) {
    const tabs = tabsContainer.querySelectorAll('.landing-role-tab');
    const panels = {
      farmer: root.querySelector('#role-panel-farmer'),
      buyer: root.querySelector('#role-panel-buyer'),
      transporter: root.querySelector('#role-panel-transporter'),
    };

    tabsContainer.addEventListener('click', (e) => {
      const tab = e.target.closest('.landing-role-tab');
      if (!tab) return;
      const targetRole = tab.dataset.tab;

      tabs.forEach(t => t.setAttribute('aria-selected', String(t === tab)));
      Object.entries(panels).forEach(([role, panel]) => {
        if (panel) panel.hidden = role !== targetRole;
      });
    });
  }

  return () => {
    root.removeEventListener('click', onAnchorClick);
  };
}
