/**
 * Sign up. Preserves the legacy three-step flow exactly, because each step
 * exists for a reason:
 *
 *   1. supabase.auth.signUp()        -- creates the auth user
 *   2. sign in if no session came back -- projects with email confirmation on
 *      return no session; without this the user is stranded mid-signup
 *   3. POST /api/auth/register       -- creates the profiles row + role detail
 *      row. Until this succeeds the account is half-created, which is exactly
 *      the state AuthProvider treats as "not signed in".
 *
 * Step 3 runs against the Identity dependency (not get_current_user), because
 * the profile it creates is the thing get_current_user requires.
 */
import { useState, type FormEvent } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { getSupabase } from '@/services/supabase/client';
import { api } from '@/services/api/client';
import { useAuth } from '@/services/auth/AuthProvider';
import { Button, Card, Field, Input, Select } from '@/components/ui';
import { AuthLayout } from './AuthLayout';
import type { MeResponse, Role } from '@/types/api';

const ROLES: Role[] = ['farmer', 'buyer', 'transporter'];

export default function Signup() {
  const { t, i18n } = useTranslation();
  const navigate = useNavigate();
  const { refresh } = useAuth();

  const [form, setForm] = useState({
    role: 'farmer' as Role,
    full_name: '', email: '', password: '',
    phone: '', district: '', state: '', pincode: '',
  });
  const [errors, setErrors] = useState<Record<string, string | undefined>>({});
  const [busy, setBusy] = useState(false);

  const set = (k: keyof typeof form) => (v: string) => {
    setForm((p) => ({ ...p, [k]: v }));
    setErrors((p) => ({ ...p, [k]: undefined, form: undefined }));
  };

  const validate = (): boolean => {
    const e: Record<string, string> = {};
    if (!form.full_name.trim()) e.full_name = t('auth.full_name_required');
    else if (form.full_name.trim().length < 2) e.full_name = t('auth.full_name_min_length');
    if (!form.email.trim()) e.email = t('auth.email_required');
    else if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(form.email.trim())) e.email = t('auth.email_invalid');
    if (!form.password) e.password = t('auth.password_required');
    else if (form.password.length < 8) e.password = t('auth.password_min_length');
    if (form.phone && !/^[6-9]\d{9}$/.test(form.phone.trim())) e.phone = t('auth.phone_invalid');
    if (form.pincode && !/^\d{6}$/.test(form.pincode.trim())) e.pincode = t('auth.pincode_invalid');
    setErrors(e);
    return Object.keys(e).length === 0;
  };

  const mapErr = (err: { message?: string }): string => {
    const m = String(err.message ?? '');
    if (m.toLowerCase().includes('already registered')) return t('auth.email_already_registered');
    if (m.includes('throttled') || m.toLowerCase().includes('too many')) return t('auth.too_many_attempts');
    return m || t('common.error_body');
  };

  const onSubmit = async (e: FormEvent) => {
    e.preventDefault();
    if (busy || !validate()) return;
    setBusy(true);
    setErrors({});

    const email = form.email.trim();
    const supabase = getSupabase();

    try {
      // Step 1 -- create the auth user.
      const { data: signUpData, error: signUpError } =
        await supabase.auth.signUp({ email, password: form.password });
      if (signUpError) throw new Error(mapErr(signUpError));

      // Step 2 -- a project with email confirmation on returns no session.
      let session = signUpData?.session ?? null;
      if (!session) {
        const { data: loginData, error: loginErr } =
          await supabase.auth.signInWithPassword({ email, password: form.password });
        if (loginErr) throw new Error(t('auth.check_email_confirmation'));
        session = loginData?.session ?? null;
      }
      if (!session) throw new Error(t('auth.signup_no_session'));

      // Step 3 -- create profiles + role detail row. Until this lands the
      // account is half-created.
      await api.post<MeResponse>('/api/auth/register', {
        role: form.role,
        full_name: form.full_name.trim(),
        phone: form.phone.trim() || null,
        district: form.district.trim() || null,
        state: form.state.trim() || null,
        pincode: form.pincode.trim() || null,
        preferred_language: i18n.language,
        role_details: {},
      });

      await refresh();
      navigate(`/${form.role}`, { replace: true });
    } catch (err) {
      setErrors({ form: mapErr(err as { message?: string }) });
    } finally {
      setBusy(false);
    }
  };

  return (
    <AuthLayout title={t('auth.signup_title')} wide>
      <Card>
        <form onSubmit={onSubmit} noValidate className="space-y-4">
          {errors.form && (
            <p role="alert" className="rounded-md bg-danger-container px-3 py-2 text-body text-danger-on-container">
              {errors.form}
            </p>
          )}

          <Field label={t('auth.role')} htmlFor="role" required>
            <Select id="role" value={form.role}
                    onChange={(e) => set('role')(e.target.value)}>
              {ROLES.map((r) => <option key={r} value={r}>{t(`auth.role_${r}`)}</option>)}
            </Select>
          </Field>

          <div className="grid gap-4 sm:grid-cols-2">
            <Field label={t('auth.full_name')} htmlFor="full_name" error={errors.full_name} required>
              <Input id="full_name" autoComplete="name" required value={form.full_name}
                     invalid={Boolean(errors.full_name)} onChange={(e) => set('full_name')(e.target.value)} />
            </Field>
            <Field label={t('auth.phone')} htmlFor="phone" error={errors.phone}>
              <Input id="phone" inputMode="numeric" autoComplete="tel" value={form.phone}
                     invalid={Boolean(errors.phone)} onChange={(e) => set('phone')(e.target.value)} />
            </Field>
          </div>

          <Field label={t('auth.email')} htmlFor="su-email" error={errors.email} required>
            <Input id="su-email" type="email" autoComplete="email" required value={form.email}
                   invalid={Boolean(errors.email)} onChange={(e) => set('email')(e.target.value)} />
          </Field>

          <Field label={t('auth.password')} htmlFor="su-password" error={errors.password}
                 hint={t('auth.password_hint')} required>
            <Input id="su-password" type="password" autoComplete="new-password" required
                   value={form.password} invalid={Boolean(errors.password)}
                   onChange={(e) => set('password')(e.target.value)} />
          </Field>

          <div className="grid gap-4 sm:grid-cols-3">
            <Field label={t('auth.district')} htmlFor="district">
              <Input id="district" value={form.district} onChange={(e) => set('district')(e.target.value)} />
            </Field>
            <Field label={t('auth.state')} htmlFor="state">
              <Input id="state" value={form.state} onChange={(e) => set('state')(e.target.value)} />
            </Field>
            <Field label={t('auth.pincode')} htmlFor="pincode" error={errors.pincode}>
              <Input id="pincode" inputMode="numeric" value={form.pincode}
                     invalid={Boolean(errors.pincode)} onChange={(e) => set('pincode')(e.target.value)} />
            </Field>
          </div>

          <Button type="submit" block loading={busy}>{t('auth.sign_up')}</Button>

          <p className="text-center text-body text-ink-muted">
            {t('auth.have_account')}{' '}
            <Link to="/login" className="font-semibold text-primary underline underline-offset-2">
              {t('auth.sign_in')}
            </Link>
          </p>
        </form>
      </Card>
    </AuthLayout>
  );
}
