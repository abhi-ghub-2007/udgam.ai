/* toast.js - transient feedback. Announced via the aria-live region in
   index.html, so screen readers get it too. */

export function toast(message, kind = 'info', ms = 4000) {
  const region = document.getElementById('toast-region');
  if (!region) return;
  const el = document.createElement('div');
  el.className = `toast toast--${kind}`;
  el.textContent = message;
  region.appendChild(el);
  setTimeout(() => el.remove(), ms);
}
