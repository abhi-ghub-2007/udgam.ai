import { Suspense } from 'react';
import { RouterProvider } from 'react-router-dom';
import { Providers } from './providers';
import { router } from './router';
import { Skeleton } from '@/components/ui';

/**
 * The root Suspense boundary.
 *
 * AppShell has its own boundary for the signed-in pages, but the PUBLIC routes
 * (/, /login, /signup) render outside the shell and are lazily imported too.
 * Without a boundary above them, a synchronous navigation to a chunk that has
 * not downloaded yet -- browser back/forward, or a redirect -- throws
 * "A component suspended while responding to synchronous input".
 */
export default function App() {
  return (
    <Providers>
      <Suspense fallback={<RootFallback />}>
        <RouterProvider router={router} />
      </Suspense>
    </Providers>
  );
}

function RootFallback() {
  return (
    <div className="mx-auto max-w-content space-y-4 p-6">
      <Skeleton className="h-8 w-40" />
      <Skeleton className="h-40" />
    </div>
  );
}
