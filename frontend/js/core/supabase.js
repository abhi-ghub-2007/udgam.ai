/* ===========================================================================
   supabase.js - Auth session handling + Storage uploads ONLY.
   plan.md section 3 permits exactly these two uses on the frontend; all
   business logic goes through FastAPI.

   The anon key is fetched at runtime from GET /api/config (A-16), never
   hardcoded here. Rotating it touches .env only. The service-role key never
   leaves the server.
   =========================================================================== */

import { createClient } from './vendor/supabase-js.esm.js';

let client = null;

/** Stand-in used before init() and when the backend is unreachable, so a
    view calling supabase.auth.getSession() never throws on a null client. */
const notReady = {
  auth: {
    getSession: async () => ({ data: { session: null } }),
    refreshSession: async () => ({ data: { session: null } }),
    signInWithPassword: async () => { throw new Error('Auth is not ready yet.'); },
    signUp: async () => { throw new Error('Auth is not ready yet.'); },
    signOut: async () => ({ error: null }),
    onAuthStateChange: () => ({ data: { subscription: { unsubscribe() {} } } }),
  },
};

export const supabase = new Proxy({}, {
  get: (_, prop) => (client ? client[prop] : notReady[prop]),
});

export async function initSupabase(apiBase) {
  const res = await fetch(`${apiBase}/api/config`);
  if (!res.ok) throw new Error('Could not reach the UDGAM API.');
  const cfg = await res.json();
  if (!cfg.configured) {
    console.warn('[supabase] backend reports Supabase is not configured');
    return { configured: false, languages: cfg.languages };
  }
  client = createClient(cfg.supabase_url, cfg.supabase_anon_key, {
    auth: { persistSession: true, autoRefreshToken: true, detectSessionInUrl: false },
  });
  return { configured: true, languages: cfg.languages };
}

/** F-2: photo upload straight to Storage, then the backend is told the path
    and runs AI-1 grading on it. */
export async function uploadProductPhoto(userId, file) {
  const ext = (file.name.split('.').pop() || 'jpg').toLowerCase();
  const path = `${userId}/${crypto.randomUUID()}.${ext}`;
  const { error } = await supabase.storage
    .from('product-photos')
    .upload(path, file, { cacheControl: '3600', upsert: false });
  if (error) throw error;
  return path;
}

export function publicPhotoUrl(path) {
  if (!path) return '';
  const { data } = supabase.storage.from('product-photos').getPublicUrl(path);
  return data?.publicUrl || '';
}
