/**
 * Supabase browser client.
 *
 * The anon key is NOT baked into the bundle. It is fetched at runtime from
 * GET /api/config, exactly as the legacy frontend did (A-16) -- this keeps the
 * key out of committed source and lets the same build point at different
 * environments. The service-role key never reaches the browser under any
 * circumstance.
 */
import { createClient, type SupabaseClient } from '@supabase/supabase-js';
import type { AppConfig } from '@/types/api';

export const API_BASE: string =
  (import.meta.env.VITE_API_BASE as string | undefined) ||
  (window as unknown as { __UDGAM_API_BASE__?: string }).__UDGAM_API_BASE__ ||
  'http://127.0.0.1:8001';

let client: SupabaseClient | null = null;
let config: AppConfig | null = null;

export function getSupabase(): SupabaseClient {
  if (!client) {
    throw new Error('Supabase client used before initSupabase() resolved.');
  }
  return client;
}

export function getConfig(): AppConfig | null {
  return config;
}

/** Fetches runtime config and builds the client. Called once, during boot. */
export async function initSupabase(): Promise<AppConfig> {
  const res = await fetch(`${API_BASE}/api/config`);
  if (!res.ok) throw new Error(`Config request failed: ${res.status}`);
  const cfg = (await res.json()) as AppConfig;
  config = cfg;

  if (cfg.configured && cfg.supabase_url && cfg.supabase_anon_key) {
    client = createClient(cfg.supabase_url, cfg.supabase_anon_key, {
      auth: { persistSession: true, autoRefreshToken: true, detectSessionInUrl: false },
    });
  }
  return cfg;
}
