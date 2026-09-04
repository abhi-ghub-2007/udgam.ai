/* C-2 Notifications, for every role. Backed by GET /api/notifications.

   Replaces the `upcoming` placeholder. Rows store an i18n KEY plus params
   rather than a rendered sentence (db/SCHEMA.sql), so a notification written
   while the user was in English still reads correctly in Hindi or Marathi.
   Unknown keys fall back to the notification `type` rather than printing a raw
   dotted key at the user.

   Also keeps the header's unread badge honest: the count in the store is
   refreshed from the same payload that renders the list. */

import { api } from '../core/api.js';
import { store } from '../core/store.js';
import { t, date } from '../core/i18n.js';
import { toast } from '../core/toast.js';

export const title = 'market.notifications_title';

let items = [];
let unread = 0;
let loadError = null;

function syncBadge(count) {
  unread = count;
  store.set('unreadCount', count);
  const badge = document.getElementById('unread-badge');
  if (badge) {
    badge.hidden = count === 0;
    badge.textContent = String(count);
  }
}

/** A stored key renders through t(); anything unrecognised degrades to the
    notification type, never to a raw `some.dotted.key` on screen. */
function line(key, params, fallback) {
  if (!key) return fallback;
  const text = t(key, params || {});
  return text === key ? fallback : text;
}

export async function render() {
  try {
    const res = await api.get('/api/notifications');
    items = res.items || [];
    loadError = null;
    syncBadge(res.unread_count || 0);
  } catch (err) {
    items = [];
    loadError = err;
  }

  if (loadError) {
    return `<div class="stack stack--lg">
      <h1>${t('market.notifications_title')}</h1>
      <div class="state state--error" role="alert">
        <p class="state__body">${loadError.message || t('common.error_body')}</p>
        <button class="btn btn--primary" data-action="retry-notifications">${t('common.retry')}</button>
      </div>
    </div>`;
  }

  return `<div class="stack stack--lg">
    <div class="row row--between row--wrap">
      <h1 style="margin:0">${t('market.notifications_title')}</h1>
      ${unread > 0
        ? `<button class="btn btn--outline" type="button" data-action="read-all">
             ${t('market.mark_all_read')}
           </button>` : ''}
    </div>
    <section id="notif-list" class="stack stack--sm">${list()}</section>
  </div>`;
}

function list() {
  if (!items.length) {
    return `<div class="state state--empty">
      <p class="state__body">${t('market.notifications_empty')}</p>
      <a class="btn btn--primary" href="#/">${t('common.go_home')}</a>
    </div>`;
  }
  return items.map(row).join('');
}

function row(n) {
  const isUnread = !n.read_at;
  return `
  <article class="card stack stack--sm" data-notification="${n.id}"
           style="${isUnread ? 'border-left:3px solid var(--c-primary)' : 'opacity:.72'}">
    <div class="row row--between row--wrap">
      <strong>${line(n.title_key, n.params, n.type || t('market.notification'))}</strong>
      <span class="card__meta">${date(n.created_at)}</span>
    </div>
    <p class="card__meta" style="margin:0">
      ${line(n.body_key, n.params, '')}
    </p>
    ${isUnread
      ? `<button class="btn btn--ghost" type="button" data-action="read" data-id="${n.id}">
           ${t('market.mark_read')}
         </button>`
      : `<span class="card__meta">${t('market.read')}</span>`}
  </article>`;
}

export function mount(root) {
  const refresh = () => {
    const listEl = root.querySelector('#notif-list');
    if (listEl) listEl.innerHTML = list();
    const btn = root.querySelector('[data-action="read-all"]');
    if (btn && unread === 0) btn.remove();
  };

  const onClick = async (e) => {
    if (e.target.closest('[data-action="retry-notifications"]')) { location.reload(); return; }

    const one = e.target.closest('[data-action="read"]');
    if (one) {
      const id = one.dataset.id;
      one.disabled = true;
      try {
        await api.post(`/api/notifications/${id}/read`, {});
        const hit = items.find((n) => String(n.id) === String(id));
        if (hit) hit.read_at = new Date().toISOString();
        syncBadge(Math.max(0, unread - 1));
        refresh();
      } catch (err) {
        one.disabled = false;
        toast(err.message || t('common.error_body'), 'error');
      }
      return;
    }

    const all = e.target.closest('[data-action="read-all"]');
    if (all) {
      all.disabled = true;
      try {
        await api.post('/api/notifications/read-all', {});
        const now = new Date().toISOString();
        items.forEach((n) => { if (!n.read_at) n.read_at = now; });
        syncBadge(0);
        refresh();
      } catch (err) {
        all.disabled = false;
        toast(err.message || t('common.error_body'), 'error');
      }
    }
  };

  root.addEventListener('click', onClick);
  return () => root.removeEventListener('click', onClick);
}
