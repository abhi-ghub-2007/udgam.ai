/**
 * The signed-in application shell: header, desktop side rail, mobile bottom nav.
 *
 * Navigation is role-specific by design -- a farmer and a transporter do
 * genuinely different jobs and should not share a generic menu. The bottom nav
 * caps at 5 items (thumb reach); anything beyond that lives in the side rail on
 * larger screens, which is why the two are generated from one list with a
 * `railOnly` flag rather than being maintained separately.
 */
import { Suspense } from 'react';
import { NavLink, Outlet, useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { useAuth } from '@/services/auth/AuthProvider';
import { useNotifications } from '@/hooks/queries';
import { LANGS, persistLang } from '@/i18n';
import { Button, cx, Skeleton } from '@/components/ui';
import type { Role } from '@/types/api';

interface NavItem { to: string; labelKey: string; icon: JSX.Element; railOnly?: boolean }

const I = {
  home: <path d="M4 11 12 4l8 7v8a1 1 0 0 1-1 1h-5v-6h-4v6H5a1 1 0 0 1-1-1Z" />,
  box: <path d="M4 4h7v7H4Zm9 0h7v7h-7ZM4 13h7v7H4Zm9 0h7v7h-7Z" />,
  rupee: <path d="M6 3h12v2h-4.2c.7.5 1.2 1.2 1.4 2H18v2h-2.8c-.4 2.3-2.3 4-4.7 4H9.9l6.4 6H13l-6.5-6.2V15H9c1.9 0 3.4-1.1 3.8-3H6V10h6.8c-.4-1.2-1.5-2-3-2H6Z" />,
  chat: <path d="M4 5h16v10H7l-3 3Z" />,
  truck: <path d="M3 6h11v9H3Zm11 3h4l3 3v3h-7Zm-7 9a2 2 0 1 0 0-4 2 2 0 0 0 0 4Zm11 0a2 2 0 1 0 0-4 2 2 0 0 0 0 4Z" />,
  bell: <path d="M12 22a2 2 0 0 0 2-2h-4a2 2 0 0 0 2 2Zm6-6V11a6 6 0 0 0-5-5.91V4a1 1 0 1 0-2 0v1.09A6 6 0 0 0 6 11v5l-1.7 1.7a1 1 0 0 0 .7 1.3h14a1 1 0 0 0 .7-1.7Z" />,
  person: <path d="M12 12a4 4 0 1 0 0-8 4 4 0 0 0 0 8Zm0 2c-4 0-8 2-8 5v1h16v-1c0-3-4-5-8-5Z" />,
  map: <path d="M9 3 3 5v16l6-2 6 2 6-2V3l-6 2Zm0 0v16m6-14v16" />,
  search: <path d="M10 4a6 6 0 1 1 0 12 6 6 0 0 1 0-12Zm0 2a4 4 0 1 0 0 8 4 4 0 0 0 0-8Zm5.7 8.3 4 4-1.4 1.4-4-4Z" />,
};

const icon = (d: JSX.Element) => (
  <svg viewBox="0 0 24 24" width="24" height="24" aria-hidden focusable="false" fill="currentColor">
    {d}
  </svg>
);

const NAV: Record<Role, NavItem[]> = {
  farmer: [
    { to: '/farmer', labelKey: 'nav.home', icon: icon(I.home) },
    { to: '/farmer/listings', labelKey: 'nav.my_listings', icon: icon(I.box) },
    { to: '/farmer/decisions', labelKey: 'decide.title', icon: icon(I.rupee) },
    { to: '/farmer/buyers', labelKey: 'nav.matching_buyers', icon: icon(I.chat) },
    { to: '/farmer/orders', labelKey: 'market.orders_title', icon: icon(I.truck) },
    { to: '/farmer/transport', labelKey: 'market.transport_title', icon: icon(I.map), railOnly: true },
  ],
  buyer: [
    { to: '/buyer', labelKey: 'nav.home', icon: icon(I.home) },
    { to: '/buyer/market', labelKey: 'nav.market', icon: icon(I.search) },
    { to: '/buyer/requests', labelKey: 'nav.my_requests', icon: icon(I.chat) },
    { to: '/buyer/orders', labelKey: 'market.orders_title', icon: icon(I.truck) },
  ],
  transporter: [
    { to: '/transporter', labelKey: 'nav.home', icon: icon(I.home) },
    { to: '/transporter/jobs', labelKey: 'transporter.available_jobs', icon: icon(I.box) },
    { to: '/transporter/capacity', labelKey: 'nav.my_routes', icon: icon(I.truck) },
    { to: '/transporter/routes', labelKey: 'transporter.route_plan', icon: icon(I.map), railOnly: true },
    { to: '/transporter/earnings', labelKey: 'transporter.earnings_summary', icon: icon(I.rupee) },
  ],
};

export function AppShell() {
  const { role, profile, signOut } = useAuth();
  const { t, i18n } = useTranslation();
  const navigate = useNavigate();
  const { data: notif } = useNotifications();
  const unread = notif?.unread_count ?? 0;

  const items = role ? NAV[role] : [];
  const bottomItems = items.filter((i) => !i.railOnly).slice(0, 5);

  const onSignOut = async () => {
    await signOut();
    navigate('/', { replace: true });
  };

  const changeLang = (code: string) => {
    void i18n.changeLanguage(code);
    persistLang(code);
  };

  const linkCls = ({ isActive }: { isActive: boolean }) =>
    cx(
      'flex items-center gap-3 rounded-md px-3 min-h-tap text-body font-medium',
      'transition-colors duration-fast ease-udgam',
      isActive ? 'bg-primary-container text-primary-on-container' : 'text-ink-muted hover:bg-surface-low',
    );

  return (
    <div className="min-h-dvh bg-bg">
      {/* ------------------------------------------------------- header --- */}
      <header className="sticky top-0 z-nav border-b border-line-card bg-surface/95 backdrop-blur">
        <div className="mx-auto flex h-nav max-w-content items-center justify-between gap-3 px-4">
          <NavLink to={role ? `/${role}` : '/'} className="flex items-center gap-2 font-bold text-ink">
            <img src="/assets/logo.svg" alt="" width={28} height={28} aria-hidden />
            <span className="text-h2">UDGAM<span className="text-primary">.ai</span></span>
          </NavLink>

          <div className="flex items-center gap-2">
            <label className="sr-only" htmlFor="lang">{t('common.language')}</label>
            <select
              id="lang"
              value={i18n.language}
              onChange={(e) => changeLang(e.target.value)}
              className="min-h-tap rounded-md border border-outline-variant bg-surface px-2 text-label"
            >
              {LANGS.map((l) => <option key={l.code} value={l.code}>{l.label}</option>)}
            </select>

            <NavLink
              to="/notifications"
              aria-label={t('nav.notifications')}
              className="relative grid h-tap w-tap place-items-center rounded-md text-ink-muted hover:bg-surface-low"
            >
              {icon(I.bell)}
              {unread > 0 && (
                <span className="absolute right-1.5 top-1.5 grid min-w-[20px] place-items-center rounded-full bg-danger px-1 text-[11px] font-bold text-danger-on">
                  {unread}
                </span>
              )}
            </NavLink>
          </div>
        </div>
      </header>

      <div className="mx-auto flex max-w-content gap-6 px-4 py-6">
        {/* --------------------------------------------------- side rail --- */}
        <aside className="hidden w-sidebar shrink-0 md:block">
          <nav aria-label={t('nav.primary')} className="sticky top-[88px] space-y-1">
            {items.map((it) => (
              <NavLink key={it.to} to={it.to} end={it.to === `/${role}`} className={linkCls}>
                {it.icon}
                <span className="truncate">{t(it.labelKey)}</span>
              </NavLink>
            ))}
            <NavLink to="/profile" className={linkCls}>
              {icon(I.person)}
              <span className="truncate">{t('nav.profile')}</span>
            </NavLink>
            <div className="pt-3">
              <Button variant="outline" block onClick={onSignOut}>{t('auth.sign_out')}</Button>
            </div>
            {profile?.full_name && (
              <p className="px-3 pt-2 text-label text-ink-muted">{profile.full_name}</p>
            )}
          </nav>
        </aside>

        {/* ------------------------------------------------------- main --- */}
        <main id="main" className="min-w-0 flex-1 pb-24 md:pb-6">
          <Suspense fallback={<PageFallback />}>
            <Outlet />
          </Suspense>
        </main>
      </div>

      {/* --------------------------------------------------- bottom nav --- */}
      <nav
        aria-label={t('nav.primary')}
        className="fixed inset-x-0 bottom-0 z-nav border-t border-line-card bg-surface md:hidden"
      >
        <div className="grid grid-cols-5">
          {bottomItems.map((it) => (
            <NavLink
              key={it.to}
              to={it.to}
              end={it.to === `/${role}`}
              className={({ isActive }) => cx(
                'flex min-h-tap flex-col items-center justify-center gap-0.5 px-1 py-2',
                'text-[11px] font-medium leading-tight text-center',
                isActive ? 'text-primary' : 'text-ink-muted',
              )}
            >
              {it.icon}
              {/* Every icon is paired with a text label -- no standalone icons. */}
              <span className="line-clamp-1">{t(it.labelKey)}</span>
            </NavLink>
          ))}
        </div>
      </nav>
    </div>
  );
}

function PageFallback() {
  return (
    <div className="space-y-4">
      <Skeleton className="h-8 w-1/3" />
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {Array.from({ length: 4 }).map((_, i) => <Skeleton key={i} className="h-24" />)}
      </div>
      <Skeleton className="h-48" />
    </div>
  );
}
