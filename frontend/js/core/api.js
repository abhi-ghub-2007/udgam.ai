/* ===========================================================================
   api.js - THE ONLY place a raw fetch() to the backend is allowed.
   PRD section 5.1: injects the bearer token, refreshes on 401, normalises the
   error envelope. No view file may call fetch() directly.
   =========================================================================== */

import { supabase } from './supabase.js';
import { store } from './store.js';

const BASE = window.__UDGAM_API_BASE__ || 'http://127.0.0.1:8001';

/** Error carrying the API_CONTRACT code so callers can branch on it. */
export class ApiError extends Error {
  constructor(code, message, field, status) {
    super(message);
    this.name = 'ApiError';
    this.code = code;
    this.field = field;
    this.status = status;
  }
  /** True when retrying might actually work (offline, upstream down). */
  get isRetryable() {
    return this.code === 'NETWORK' || this.code === 'UPSTREAM_UNAVAILABLE' || this.status >= 500;
  }
}

async function token() {
  // Read the cached session first. supabase-js serialises getSession() behind
  // an auth lock, so calling it once per request deadlocks as soon as a screen
  // fires two fetches at the same time (a dashboard easily fires four). app.js
  // keeps `session` current from onAuthStateChange, so the store is both the
  // faster and the safer source; getSession() stays as the cold-start path.
  const cached = store.get('session')?.access_token;
  if (cached) return cached;

  const { data } = await supabase.auth.getSession();
  if (data?.session) store.set('session', data.session);
  return data?.session?.access_token || null;
}

async function raw(path, { method = 'GET', body, headers = {}, retryOn401 = true } = {}) {
  const jwt = await token();
  // FormData must go out untouched: the browser sets multipart/form-data with
  // the boundary, and JSON.stringify would destroy the file.
  const isForm = body instanceof FormData;
  const opts = {
    method,
    headers: {
      Accept: 'application/json',
      ...(body !== undefined && !isForm ? { 'Content-Type': 'application/json' } : {}),
      ...(jwt ? { Authorization: `Bearer ${jwt}` } : {}),
      ...headers,
    },
    ...(body !== undefined ? { body: isForm ? body : JSON.stringify(body) } : {}),
  };

  let res;
  try {
    res = await fetch(`${BASE}${path}`, opts);
  } catch {
    // Offline or the API is not running. C-5 shows the cached payload here.
    throw new ApiError('NETWORK', 'You appear to be offline. Check your connection.', null, 0);
  }

  // One transparent retry after refreshing an expired session. The refreshed
  // session goes into the store so token() above picks it up immediately.
  if (res.status === 401 && retryOn401 && !path.startsWith('/api/auth/')) {
    const { data } = await supabase.auth.refreshSession();
    if (data?.session) {
      store.set('session', data.session);
      return raw(path, { method, body, headers, retryOn401: false });
    }
  }

  if (res.status === 204) return null;

  let payload = null;
  try { payload = await res.json(); } catch { /* empty or non-JSON body */ }

  if (!res.ok) {
    const e = payload?.error || {};
    throw new ApiError(
      e.code || 'INTERNAL',
      e.message || 'Something went wrong. Please try again.',
      e.field || null,
      res.status,
    );
  }
  return payload;
}

const qs = (params) => {
  if (!params) return '';
  const s = new URLSearchParams(
    Object.entries(params).filter(([, v]) => v !== undefined && v !== null && v !== ''),
  ).toString();
  return s ? `?${s}` : '';
};

export const api = {
  get:    (path, params)  => raw(path + qs(params)),
  post:   (path, body, h) => raw(path, { method: 'POST',   body, headers: h }),
  /** Multipart POST (photo upload). Body must be a FormData. */
  postForm: (path, formData) => raw(path, { method: 'POST', body: formData }),
  patch:  (path, body)    => raw(path, { method: 'PATCH',  body }),
  put:    (path, body)    => raw(path, { method: 'PUT',    body }),
  delete: (path)          => raw(path, { method: 'DELETE' }),

  /** Idempotency-Key for money-moving and state-advancing POSTs. */
  postOnce: (path, body) =>
    raw(path, { method: 'POST', body, headers: { 'Idempotency-Key': crypto.randomUUID() } }),
};
