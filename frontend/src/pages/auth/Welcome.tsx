/**
 * The optional identity step, immediately after signup.
 *
 * WHY IT IS A ROUTE AND NOT A STAGE INSIDE Signup
 * ------------------------------------------------
 * Signup lives behind `PublicOnly`, which redirects any signed-in user to
 * their dashboard. The moment account creation finishes and AuthProvider
 * refreshes, that guard fires -- so a stage rendered inside Signup is
 * unreachable by construction. Found by actually running a signup: the step
 * never appeared and the user landed straight on /farmer.
 *
 * It therefore lives here, inside the authenticated shell, and Signup
 * navigates to it. The account is already complete before this renders, which
 * is what makes skipping safe: every exit leads to the dashboard.
 *
 * No AuthLayout here either -- that renders its own header, and inside
 * AppShell that produced two stacked headers and a doubled title.
 */
import { useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { useAuth } from '@/services/auth/AuthProvider';
import { PageHeader } from '@/components/ui';
import { SignupIdentityStep } from './SignupIdentityStep';

export default function Welcome() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const { profile } = useAuth();
  const home = profile?.role ? `/${profile.role}` : '/';

  return (
    <div className="space-y-6">
      <PageHeader
        title={t('signup_identity.welcome_title', { name: profile?.full_name ?? '' })}
        subtitle={t('signup_identity.welcome_subtitle')}
      />
      <div className="max-w-xl">
        <SignupIdentityStep onDone={() => navigate(home, { replace: true })} />
      </div>
    </div>
  );
}
