/* Screens whose backend lands in a later phase (orders → Phase 4, transport →
   Phase 5, notifications → Phase 6).

   These are deliberately honest: they explain what the screen will hold and
   what has to happen first, and they link to the action that actually moves
   the farmer forward today. They are reachable from the nav, so the nav has no
   dead ends — but nothing here pretends to be live data. */

import { t } from '../../core/i18n.js';

const SCREENS = {
  orders: {
    title: 'market.orders_title',
    body: 'market.orders_empty',
    href: '#/farmer/buyers',
    cta: 'market.matching_title',
  },
  transport: {
    title: 'market.transport_title',
    body: 'market.transport_empty',
    href: '#/farmer/orders',
    cta: 'market.orders_title',
  },
  notifications: {
    title: 'market.notifications_title',
    body: 'market.notifications_empty',
    href: '#/farmer',
    cta: 'nav.home',
  },
};

export function make(key) {
  const s = SCREENS[key];
  return {
    title: s.title,
    render() {
      return `
      <div class="stack stack--lg">
        <h1>${t(s.title)}</h1>
        <div class="state state--empty">
          <p class="state__body">${t(s.body)}</p>
          <a class="btn btn--primary" href="${s.href}">${t(s.cta)}</a>
        </div>
      </div>`;
    },
  };
}
