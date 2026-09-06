/**
 * Authentication state for the whole app.
 *
 * Mirrors the legacy frontend/js/app.js boot + onAuthStateChange flow exactly,
 * because that flow encodes several hard-won behaviours:
 *
 *  - The access token is pushed into the API client's cache on every auth
 *    event. The API client must never call getSession() per request (see the
 *    note in services/api/client.ts about the supabase-js auth lock).
 *  - A session with no profile row means signup never finished; the user is
 *    treated as signed-out for routing purposes rather than being trapped in a
 *    half-registered state.
 *  - SIGNED_IN during signup is ignored, because the signup page creates the
 *    profile itself and re-entrancy here would race it.
 *
 * SECURITY: `role` here drives NAVIGATION ONLY. It is UX protection, not the
 * security boundary -- every endpoint independently re-derives the caller's
 * role from their JWT and Postgres RLS enforces it. Nothing in this file is
 * trusted by the backend.
 */
import {
  createContext, useCallback, useContext, useEffect, useMemo, useRef, useState,
  type ReactNode,
} from 'react';
import type { Session } from '@supabase/supabase-js';
import { getSupabase } from '@/services/supabase/client';
import { api, setCachedToken } from '@/services/api/client';
import i18n, { persistLang } from '@/i18n';
import type { MeResponse, Profile, Role } from '@/types/api';

interface AuthState {
  session: Session | null;
  profile: Profile | null;
  details: Record<string, unknown>;
  isFpo: boolean;
  role: Role | null;
  /** True until the first session resolution completes. Guards route redirects. */
  loading: boolean;
  signedIn: boolean;
  refresh: () => Promise<void>;
  signOut: () => Promise<void>;
}

const AuthContext = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [session, setSession] = useState<Session | null>(null);
  const [profile, setProfile] = useState<Profile | null>(null);
  const [details, setDetails] = useState<Record<string, unknown>>({});
  const [isFpo, setIsFpo] = useState(false);
  const [loading, setLoading] = useState(true);
  const mounted = useRef(true);

  /** Loads the profile for the current session. Safe to call repeatedly. */
  const loadProfile = useCallback(async (s: Session | null) => {
    setCachedToken(s?.access_token ?? null);
    if (!s) {
      setProfile(null);
      setDetails({});
      setIsFpo(false);
      return;
    }
    try {
      const me = await api.get<MeResponse>('/api/auth/me');
      if (!mounted.current) return;
      setProfile(me.profile);
      setDetails(me.details ?? {});
      setIsFpo(Boolean(me.is_fpo));
      const pref = me.profile?.preferred_language;
      if (pref && pref !== i18n.language) {
        void i18n.changeLanguage(pref);
        persistLang(pref);
      }
    } catch {
      // A session with no profile row means signup never finished.
      if (!mounted.current) return;
      setProfile(null);
      setDetails({});
      setIsFpo(false);
    }
  }, []);

  useEffect(() => {
    mounted.current = true;
    let unsub: (() => void) | undefined;

    void (async () => {
      let supabase;
      try {
        supabase = getSupabase();
      } catch {
        // Supabase unconfigured: the app shows the setup screen, not a crash.
        if (mounted.current) setLoading(false);
        return;
      }

      const { data } = await supabase.auth.getSession();
      const s = data?.session ?? null;
      if (mounted.current) setSession(s);
      await loadProfile(s);
      if (mounted.current) setLoading(false);

      const { data: sub } = supabase.auth.onAuthStateChange((event, next) => {
        if (event === 'SIGNED_OUT') {
          setSession(null);
          setCachedToken(null);
          setProfile(null);
          setDetails({});
          setIsFpo(false);
          return;
        }
        if (event === 'SIGNED_IN') {
          // The signup page creates the profile itself; re-entering here races it.
          if (window.location.pathname.startsWith('/signup')) {
            setSession(next ?? null);
            setCachedToken(next?.access_token ?? null);
            return;
          }
          setSession(next ?? null);
          void loadProfile(next ?? null);
          return;
        }
        if (event === 'TOKEN_REFRESHED') {
          setSession(next ?? null);
          setCachedToken(next?.access_token ?? null);
        }
      });
      unsub = () => sub.subscription.unsubscribe();
    })();

    return () => {
      mounted.current = false;
      unsub?.();
    };
  }, [loadProfile]);

  const refresh = useCallback(async () => {
    const { data } = await getSupabase().auth.getSession();
    const s = data?.session ?? null;
    setSession(s);
    await loadProfile(s);
  }, [loadProfile]);

  const signOut = useCallback(async () => {
    try {
      await getSupabase().auth.signOut();
    } finally {
      setCachedToken(null);
      setSession(null);
      setProfile(null);
      setDetails({});
      setIsFpo(false);
    }
  }, []);

  const value = useMemo<AuthState>(
    () => ({
      session,
      profile,
      details,
      isFpo,
      role: profile?.role ?? null,
      loading,
      // Both are required: a session without a profile is a half-finished
      // signup, not a signed-in user.
      signedIn: Boolean(session && profile),
      refresh,
      signOut,
    }),
    [session, profile, details, isFpo, loading, refresh, signOut],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthState {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used inside <AuthProvider>');
  return ctx;
}
