import { useEffect, useState, type ReactNode } from 'react';
import { QueryClientProvider } from '@tanstack/react-query';
import { useTranslation } from 'react-i18next';
import { queryClient } from './queryClient';
import { AuthProvider } from '@/services/auth/AuthProvider';
import { initSupabase } from '@/services/supabase/client';
import { Skeleton } from '@/components/ui';

/**
 * Boot gate. Supabase config is fetched at runtime (the anon key is not baked
 * into the bundle), so nothing that needs a Supabase client may render until
 * initSupabase() resolves. Failure here is shown as a designed screen, not a
 * blank page or a stack trace.
 */
export function Providers({ children }: { children: ReactNode }) {
  const [state, setState] = useState<'loading' | 'ready' | 'error' | 'unconfigured'>('loading');
  const { t } = useTranslation();

  useEffect(() => {
    let alive = true;
    void initSupabase()
      .then((cfg) => { if (alive) setState(cfg.configured ? 'ready' : 'unconfigured'); })
      .catch((err) => {
        console.error('[boot] initSupabase failed:', err);
        if (alive) setState('error');
      });
    return () => { alive = false; };
  }, []);

  if (state === 'loading') {
    return (
      <div className="mx-auto max-w-content space-y-4 p-6">
        <Skeleton className="h-8 w-40" />
        <Skeleton className="h-40" />
      </div>
    );
  }

  if (state !== 'ready') {
    const isError = state === 'error';
    return (
      <div className="grid min-h-dvh place-items-center bg-bg p-6">
        <div role="alert" className="max-w-md space-y-3 rounded-lg border-card border-danger/30 bg-surface p-6 text-center">
          <h1 className="text-h1 font-bold text-ink">
            {t(isError ? 'common.api_down_title' : 'common.setup_title')}
          </h1>
          <p className="text-body text-ink-muted">
            {t(isError ? 'common.api_down_body' : 'common.setup_body')}
          </p>
          {isError && (
            <button
              onClick={() => location.reload()}
              className="min-h-tap-primary rounded-md bg-primary px-5 font-semibold text-primary-on"
            >
              {t('common.retry')}
            </button>
          )}
        </div>
      </div>
    );
  }

  return (
    <QueryClientProvider client={queryClient}>
      <AuthProvider>{children}</AuthProvider>
    </QueryClientProvider>
  );
}
