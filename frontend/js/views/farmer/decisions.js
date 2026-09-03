/* Market Decision Center (SIH26132 §11).

   Answers one question for one lot: "what should I do with this crop right now?"
   Best exit, sell-now-vs-wait, and how the markets compare — each with where the
   number came from and how much to trust it.

   Built from the existing design system only: .card, .badge, .tile, .stack,
   .grid, .state, .reasons. No new visual language, no new dependency.

   FAILURE ISOLATION (§19): every panel fetches independently and renders its own
   error or empty state. A market-data outage degrades one card; it never blanks
   the page and never touches the rest of the farmer's dashboard, which does not
   call these endpoints at all. */

import { api } from '../../core/api.js';
import { store } from '../../core/store.js';
import { t, money, number } from '../../core/i18n.js';

export const title = 'decide.title';

let lots = [];
let selected = null;

/** Freshness/method badge. The honesty label travels with every figure. */
function provenance(p) {
  if (!p) return '';
  const fresh = p.freshness || 'STALE';
  const tone = fresh === 'LIVE' ? 'success'
             : fresh === 'RECENT' ? 'info'
             : fresh === 'SYNTHETIC' ? 'warning'
             : fresh === 'ESTIMATED' ? 'warning' : 'error';
  const bits = [`<span class="badge badge--${tone}">${t(`decide.freshness.${fresh}`)}</span>`];
  if (p.method) bits.push(`<span class="badge badge--method">${t(`ai.method_${p.method}`)}</span>`);
  if (p.source) bits.push(`<span class="card__meta">${t('decide.source')}: ${p.source}</span>`);
  if (p.confidence != null) {
    bits.push(`<span class="card__meta">${t('decide.confidence')}: ${Math.round(p.confidence * 100)}%</span>`);
  }
  return `<div class="row row--wrap" style="gap:var(--sp-xs);align-items:center">${bits.join('')}</div>`;
}

function errorCard(titleKey, err) {
  return `<div class="card stack stack--sm">
    <h3 class="card__title">${t(titleKey)}</h3>
    <p class="state__body">${err?.message || t('decide.unavailable')}</p>
    <span class="card__meta">${t('decide.unavailable_hint')}</span>
  </div>`;
}

/* ------------------------------------------------------------ best exit ---- */
function breakdownRow(l) {
  const sign = l.kind === 'gross' ? '' : '−';
  const dim = l.reduces_farmer_net ? '' : ' style="opacity:.62"';
  return `<tr${dim}>
    <td>${l.label}${l.reduces_farmer_net ? '' : ` <span class="card__meta">(${t('decide.paid_by', { who: t(`decide.bearer.${l.borne_by}`) })})</span>`}</td>
    <td class="num">${sign}${money(l.amount_paise)}</td>
  </tr>`;
}

function bestExitCard(d) {
  if (!d || d.availability !== 'ok' || !d.best) {
    return `<div class="card stack stack--sm">
      <h3 class="card__title">${t('decide.best_exit')}</h3>
      <p class="state__body">${t('decide.no_exit')}</p>
    </div>`;
  }
  const b = d.best;
  return `
  <section class="card stack">
    <div class="row row--between">
      <h3 class="card__title">${t('decide.best_exit')}</h3>
      <span class="badge badge--method">${t(`ai.method_${d.method}`)}</span>
    </div>

    <div>
      <p class="tile__label">${b.reference_name} · ${t(`decide.channel.${b.channel}`)}</p>
      <p class="tile__value">${money(b.net_realization_paise)}</p>
      <p class="card__meta">${t('decide.expected_net')}</p>
    </div>

    <div class="table-scroll">
      <table class="breakdown">
        <caption class="sr-only">${t('decide.how_calculated')}</caption>
        <tbody>
          ${(b.breakdown || []).map(breakdownRow).join('')}
          <tr class="breakdown__total">
            <td>${t('decide.expected_net')}</td>
            <td class="num">${money(b.net_realization_paise)}</td>
          </tr>
        </tbody>
      </table>
    </div>

    ${b.reasons?.length ? `<ul class="reasons">${b.reasons.map((r) => `<li>${r}</li>`).join('')}</ul>` : ''}
    ${b.limitations?.length ? `<ul class="reasons reasons--warn">${b.limitations.map((r) => `<li>${r}</li>`).join('')}</ul>` : ''}
    ${provenance(b.price_provenance)}

    ${d.ranked?.length > 1 ? `
      <details class="disclosure">
        <summary>${t('decide.compare_options', { n: d.ranked.length })}</summary>
        <div class="table-scroll">
          <table class="breakdown">
            <thead><tr><th>${t('decide.option')}</th><th class="num">${t('decide.expected_net')}</th><th class="num">${t('decide.distance')}</th></tr></thead>
            <tbody>${d.ranked.map((o) => `<tr>
              <td>${o.reference_name}<br><span class="card__meta">${t(`decide.channel.${o.channel}`)}</span></td>
              <td class="num">${money(o.net_realization_paise)}</td>
              <td class="num">${o.distance_km != null ? `${number(Math.round(o.distance_km))} km` : '—'}</td>
            </tr>`).join('')}</tbody>
          </table>
        </div>
        <p class="card__meta">${t('decide.ranked_by')}: ${d.ranked_by}</p>
      </details>` : ''}

    ${d.excluded?.length ? `
      <details class="disclosure">
        <summary>${t('decide.excluded_options', { n: d.excluded.length })}</summary>
        <ul class="reasons">${d.excluded.map((o) =>
          `<li>${o.reference_name}: ${(o.blockers?.[0] || o.limitations?.[0] || '')}</li>`).join('')}</ul>
      </details>` : ''}

    ${d.neutrality ? `<p class="card__meta">${d.neutrality.statement}</p>` : ''}
  </section>`;
}

/* --------------------------------------------------------- sale window ----- */
function saleWindowCard(d) {
  if (!d || d.availability !== 'ok' || !d.scenarios?.length) {
    return `<div class="card stack stack--sm">
      <h3 class="card__title">${t('decide.sell_or_wait')}</h3>
      <p class="state__body">${t('decide.no_window')}</p>
    </div>`;
  }
  const verdict = d.recommendation === 'sell_now'
    ? t('decide.verdict_sell_now') : t('decide.verdict_wait');
  return `
  <section class="card stack">
    <div class="row row--between">
      <h3 class="card__title">${t('decide.sell_or_wait')}</h3>
      <span class="badge badge--method">${t(`ai.method_${d.method}`)}</span>
    </div>
    <p class="tile__value" style="font-size:var(--fs-h2)">${verdict}</p>

    <div class="table-scroll">
      <table class="breakdown">
        <thead><tr>
          <th>${t('decide.scenario')}</th>
          <th class="num">${t('decide.net')}</th>
          <th class="num">${t('decide.risk_charge')}</th>
          <th class="num">${t('decide.risk_adjusted')}</th>
        </tr></thead>
        <tbody>
          ${d.scenarios.map((s) => `<tr${s.reference_id === d.best?.reference_id ? ' class="breakdown__total"' : ''}>
            <td>${s.reference_name}${s.storage_cost_paise ? `<br><span class="card__meta">${t('decide.storage')}: ${money(s.storage_cost_paise)}</span>` : ''}</td>
            <td class="num">${money(s.net_realization_paise)}</td>
            <td class="num">${s.risk_penalty_paise ? `−${money(s.risk_penalty_paise)}` : '—'}</td>
            <td class="num">${money(s.risk_adjusted_paise)}</td>
          </tr>`).join('')}
        </tbody>
      </table>
    </div>

    ${d.best?.risk_notes?.length
      ? `<ul class="reasons">${d.best.risk_notes.map((r) => `<li>${r}</li>`).join('')}</ul>` : ''}

    ${d.excluded?.length ? `
      <details class="disclosure">
        <summary>${t('decide.not_possible', { n: d.excluded.length })}</summary>
        <ul class="reasons reasons--warn">${d.excluded.map((s) =>
          `<li>${s.reference_name}: ${(s.blockers?.[0] || s.limitations?.[0] || '')}</li>`).join('')}</ul>
      </details>` : ''}

    <p class="card__meta">${t('decide.risk_explainer')}</p>
  </section>`;
}

/* ------------------------------------------------------ market compare ----- */
function marketsCard(d) {
  if (!d || d.availability !== 'ok' || !d.markets?.length) {
    return `<div class="card stack stack--sm">
      <h3 class="card__title">${t('decide.markets')}</h3>
      <p class="state__body">${t('decide.no_markets')}</p>
    </div>`;
  }
  const arrow = (dir) => dir === 'rising' ? '↑' : dir === 'falling' ? '↓' : '→';
  return `
  <section class="card stack">
    <h3 class="card__title">${t('decide.markets')}</h3>
    <div class="table-scroll">
      <table class="breakdown">
        <thead><tr>
          <th>${t('decide.market')}</th>
          <th class="num">${t('decide.price')}</th>
          <th class="num">${t('decide.trend')}</th>
          <th class="num">${t('decide.distance')}</th>
        </tr></thead>
        <tbody>${d.markets.map((m) => `<tr>
          <td>${m.district}</td>
          <td class="num">${money(m.modal_price_paise)}</td>
          <td class="num">${arrow(m.trend?.direction)} ${m.trend?.change_pct != null ? `${m.trend.change_pct}%` : ''}</td>
          <td class="num">${m.distance_km != null ? `${number(Math.round(m.distance_km))} km` : '—'}</td>
        </tr>`).join('')}</tbody>
      </table>
    </div>
    ${provenance(d.markets[0]?.provenance)}
    <p class="card__meta">${t('decide.ranked_by')}: ${d.ranked_by}</p>
  </section>`;
}

/* ------------------------------------------------------------- render ----- */
export async function render() {
  try {
    const res = await api.get('/api/products/mine');
    lots = (res.products || []).filter((p) => p.status === 'active');
  } catch {
    lots = [];
  }

  if (!lots.length) {
    return `<div class="stack stack--lg">
      <h1>${t('decide.title')}</h1>
      <div class="state state--empty">
        <h2 class="state__title">${t('decide.no_lots_title')}</h2>
        <p class="state__body">${t('decide.no_lots_body')}</p>
        <a class="btn btn--primary" href="#/farmer/listings/new">${t('market.list_new')}</a>
      </div>
    </div>`;
  }

  selected = selected && lots.some((l) => l.id === selected) ? selected : lots[0].id;

  return `<div class="stack stack--lg">
    <div class="stack stack--sm">
      <h1>${t('decide.title')}</h1>
      <p class="state__body">${t('decide.subtitle')}</p>
    </div>

    <div class="field">
      <label class="field__label" for="lot-select">${t('decide.choose_lot')}</label>
      <select class="select" id="lot-select">
        ${lots.map((l) => `<option value="${l.id}" ${l.id === selected ? 'selected' : ''}>
          ${l.crop_name || l.crop_code || ''} · ${number(l.available_quantity_kg)} ${t('common.kg')}
          ${l.grade ? `· ${t('product.grade')} ${l.grade}` : ''}
        </option>`).join('')}
      </select>
    </div>

    <div id="decision-panels" class="stack stack--lg">
      <div class="skeleton skeleton--card"></div>
    </div>
  </div>`;
}

export function mount(root) {
  const select = root.querySelector('#lot-select');
  const panels = root.querySelector('#decision-panels');
  if (!select || !panels) return undefined;

  let token = 0;

  async function load(productId) {
    const mine = ++token;
    panels.innerHTML = `<div class="skeleton skeleton--card"></div>
                        <div class="skeleton skeleton--card"></div>`;

    const lot = lots.find((l) => l.id === productId) || {};
    const district = lot.district || store.get('profile')?.district;

    // Independent settlement: one failing panel never blanks the others.
    const [exit, window_, markets] = await Promise.allSettled([
      api.get('/api/decisions/net-exit', { product_id: productId }),
      api.get('/api/decisions/sale-window', { product_id: productId }),
      lot.crop_id
        ? api.get('/api/market/compare', { crop_id: lot.crop_id, from_district: district })
        : Promise.resolve(null),
    ]);
    if (mine !== token) return;   // a newer selection is already in flight

    panels.innerHTML = [
      exit.status === 'fulfilled' ? bestExitCard(exit.value)
                                  : errorCard('decide.best_exit', exit.reason),
      window_.status === 'fulfilled' ? saleWindowCard(window_.value)
                                     : errorCard('decide.sell_or_wait', window_.reason),
      markets.status === 'fulfilled' ? marketsCard(markets.value)
                                     : errorCard('decide.markets', markets.reason),
    ].join('');
  }

  const onChange = (e) => { selected = e.target.value; load(selected); };
  select.addEventListener('change', onChange);
  load(selected);

  return () => { token++; select.removeEventListener('change', onChange); };
}
