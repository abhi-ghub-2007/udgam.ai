/**
 * The ONLY place a raw fetch() to the backend is allowed.
 *
 * Ported from the legacy frontend/js/core/api.js with its behaviour preserved
 * exactly -- every subtlety below was load-bearing there and is load-bearing
 * here:
 *
 *  - The bearer token is read from a cached session FIRST. supabase-js
 *    serialises getSession() behind an auth lock, so calling it once per
 *    request deadlocks the moment a screen fires two fetches at once (a
 *    dashboard easily fires four, and with TanStack Query that is now the
 *    normal case, not the exception). getSession() remains the cold-start path.
 *  - FormData goes out untouched: the browser must set multipart/form-data with
 *    its own boundary, and JSON.stringify would destroy the file.
 *  - Exactly one transparent retry after refreshing an expired session, and
 *    never on /api/auth/* (which would recurse).
 *  - Errors are normalised into ApiError carrying the backend's contract code,
 *    so callers branch on `code`, not on message text.
 */
import { getSupabase } from '@/services/supabase/client';
import { API_BASE } from '@/services/supabase/client';

/** Error carrying the API_CONTRACT code so callers can branch on it. */
export class ApiError extends Error {
  readonly code: string;
  readonly field: string | null;
  readonly status: number;

  constructor(code: string, message: string, field: string | null, status: number) {
    super(message);
    this.name = 'ApiError';
    this.code = code;
    this.field = field;
    this.status = status;
  }

  /** True when retrying might actually work (offline, upstream down). */
  get isRetryable(): boolean {
    return this.code === 'NETWORK' || this.code === 'UPSTREAM_UNAVAILABLE' || this.status >= 500;
  }
}

/** Session cache, kept current by the auth provider's onAuthStateChange. */
let cachedAccessToken: string | null = null;
export function setCachedToken(token: string | null): void {
  cachedAccessToken = token;
}

async function token(): Promise<string | null> {
  if (cachedAccessToken) return cachedAccessToken;
  try {
    const { data } = await getSupabase().auth.getSession();
    if (data?.session) {
      cachedAccessToken = data.session.access_token;
      return cachedAccessToken;
    }
  } catch {
    // Supabase not configured yet; public endpoints still work unauthenticated.
  }
  return null;
}

interface RawOptions {
  method?: string;
  body?: unknown;
  headers?: Record<string, string>;
  retryOn401?: boolean;
}

async function raw<T>(path: string, opts: RawOptions = {}): Promise<T> {
  const { method = 'GET', body, headers = {}, retryOn401 = true } = opts;
  const jwt = await token();
  const isForm = body instanceof FormData;

  const init: RequestInit = {
    method,
    headers: {
      Accept: 'application/json',
      ...(body !== undefined && !isForm ? { 'Content-Type': 'application/json' } : {}),
      ...(jwt ? { Authorization: `Bearer ${jwt}` } : {}),
      ...headers,
    },
    ...(body !== undefined
      ? { body: isForm ? (body as FormData) : JSON.stringify(body) }
      : {}),
  };

  let res: Response;
  try {
    res = await fetch(`${API_BASE}${path}`, init);
  } catch {
    // Offline, or the API is not running.
    throw new ApiError('NETWORK', 'You appear to be offline. Check your connection.', null, 0);
  }

  if (res.status === 401 && retryOn401 && !path.startsWith('/api/auth/')) {
    try {
      const { data } = await getSupabase().auth.refreshSession();
      if (data?.session) {
        cachedAccessToken = data.session.access_token;
        return raw<T>(path, { method, body, headers, retryOn401: false });
      }
    } catch {
      // fall through to the normal error path
    }
  }

  if (res.status === 204) return null as T;

  let payload: unknown = null;
  try {
    payload = await res.json();
  } catch {
    // empty or non-JSON body
  }

  if (!res.ok) {
    const e = (payload as { error?: { code?: string; message?: string; field?: string } })?.error ?? {};
    throw new ApiError(
      e.code || 'INTERNAL',
      e.message || 'Something went wrong. Please try again.',
      e.field || null,
      res.status,
    );
  }
  return payload as T;
}

type QueryParams = Record<string, string | number | boolean | null | undefined>;

const qs = (params?: QueryParams): string => {
  if (!params) return '';
  const entries = Object.entries(params).filter(
    ([, v]) => v !== undefined && v !== null && v !== '',
  ) as [string, string | number | boolean][];
  const s = new URLSearchParams(entries.map(([k, v]) => [k, String(v)])).toString();
  return s ? `?${s}` : '';
};

export const api = {
  get: <T>(path: string, params?: QueryParams) => raw<T>(path + qs(params)),
  post: <T>(path: string, body?: unknown, headers?: Record<string, string>) =>
    raw<T>(path, { method: 'POST', body, headers }),
  /** Multipart POST (photo upload). Body must be a FormData. */
  postForm: <T>(path: string, formData: FormData) =>
    raw<T>(path, { method: 'POST', body: formData }),
  patch: <T>(path: string, body?: unknown) => raw<T>(path, { method: 'PATCH', body }),
  put: <T>(path: string, body?: unknown) => raw<T>(path, { method: 'PUT', body }),
  delete: <T>(path: string) => raw<T>(path, { method: 'DELETE' }),

  /** Idempotency-Key for money-moving and state-advancing POSTs. */
  postOnce: <T>(path: string, body?: unknown) =>
    raw<T>(path, { method: 'POST', body, headers: { 'Idempotency-Key': crypto.randomUUID() } }),
};
