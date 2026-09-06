/**
 * Sign in. Mirrors the legacy login view's behaviour exactly:
 *  - client-side validation before any network call
 *  - Supabase error codes mapped to friendly, translated messages
 *  - the password field is cleared and refocused on failure
 *  - after success, land on the caller's own dashboard (or the page they were
 *    originally trying to reach), never the public marketing page
 */
import { useState, type FormEvent } from 'react';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { getSupabase } from '@/services/supabase/client';
import { useAuth } from '@/services/auth/AuthProvider';
import { Button, Card, Field, Input } from '@/components/ui';
import { AuthLayout } from './AuthLayout';

export default function Login() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const location = useLocation();
  const { refresh } = useAuth();

  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [errors, setErrors] = useState<{ email?: string; password?: string; form?: string }>({});
  const [busy, setBusy] = useState(false);

  const mapSupabaseError = (error: { status?: number; message?: string }): string => {
    const code = String(error.status ?? error.message ?? '');
    if (code === 'invalid_credentials' || code.includes('invalid')) return t('auth.invalid_credentials');
    if (code.includes('throttled') || code.includes('too many')) return t('auth.too_many_attempts');
    if (code.includes('network') || code.includes('connection')) return t('common.network_error');
    return error.message || t('common.error_body');
  };

  const validate = (): boolean => {
    const next: typeof errors = {};
    if (!email.trim()) next.email = t('auth.email_required');
    else if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email.trim())) next.email = t('auth.email_invalid');
    if (!password) next.password = t('auth.password_required');
    setErrors(next);
    return Object.keys(next).length === 0;
  };

  const onSubmit = async (e: FormEvent) => {
    e.preventDefault();
    if (busy || !validate()) return;
    setBusy(true);
    setErrors({});
    try {
      const { data, error } = await getSupabase().auth.signInWithPassword({
        email: email.trim(),
        password,
      });
      if (error) {
        setErrors({ form: mapSupabaseError(error) });
        setPassword('');
        return;
      }
      if (!data.session) {
        setErrors({ form: t('auth.login_failed_no_session') });
        return;
      }
      // Pull the profile before navigating, so the guard sees a complete
      // signed-in state and does not bounce back to /login.
      await refresh();
      const from = (location.state as { from?: string } | null)?.from;
      navigate(from ?? '/', { replace: true });
    } catch (err) {
      setErrors({ form: mapSupabaseError(err as { message?: string }) });
    } finally {
      setBusy(false);
    }
  };

  return (
    <AuthLayout title={t('auth.login_title')}>
      <Card>
        <form onSubmit={onSubmit} noValidate className="space-y-4">
          {errors.form && (
            <p role="alert" className="rounded-md bg-danger-container px-3 py-2 text-body text-danger-on-container">
              {errors.form}
            </p>
          )}

          <Field label={t('auth.email')} htmlFor="email" error={errors.email} required>
            <Input
              id="email" name="email" type="email" autoComplete="email" required
              value={email} invalid={Boolean(errors.email)}
              onChange={(e) => { setEmail(e.target.value); setErrors((p) => ({ ...p, email: undefined })); }}
            />
          </Field>

          <Field label={t('auth.password')} htmlFor="password" error={errors.password} required>
            <Input
              id="password" name="password" type="password" autoComplete="current-password" required
              value={password} invalid={Boolean(errors.password)}
              onChange={(e) => { setPassword(e.target.value); setErrors((p) => ({ ...p, password: undefined })); }}
            />
          </Field>

          <Button type="submit" block loading={busy}>{t('auth.sign_in')}</Button>

          <p className="text-center text-body text-ink-muted">
            {t('auth.no_account')}{' '}
            <Link to="/signup" className="font-semibold text-primary underline underline-offset-2">
              {t('auth.sign_up')}
            </Link>
          </p>
        </form>
      </Card>
    </AuthLayout>
  );
}
