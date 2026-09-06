import { QueryClient } from '@tanstack/react-query';
import { ApiError } from '@/services/api/client';

/**
 * Server-state defaults.
 *
 * staleTime is deliberately non-zero: this app is used on rural connections
 * where every avoided round-trip matters, and the underlying Supabase calls
 * cost 300-400ms each. Retrying a 401/403/404 is pointless and would just
 * multiply that cost, so only genuinely retryable failures are retried.
 */
export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 30_000,
      gcTime: 5 * 60_000,
      refetchOnWindowFocus: false,
      retry: (failureCount, error) => {
        if (error instanceof ApiError && !error.isRetryable) return false;
        return failureCount < 2;
      },
    },
    mutations: { retry: false },
  },
});
