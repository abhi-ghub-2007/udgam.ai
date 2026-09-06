import { useEffect, useState, type FormEvent } from 'react';
import { useTranslation } from 'react-i18next';
import { useUpdateProfile } from '@/hooks/queries';
import { useAuth } from '@/services/auth/AuthProvider';
import { ApiError } from '@/services/api/client';
import { LANGS, persistLang } from '@/i18n';
import { Badge, Button, Card, Field, Input, PageHeader, Select } from '@/components/ui';

export default function Profile() {
  const { t, i18n } = useTranslation();
  const { profile, isFpo, refresh } = useAuth();
  const update = useUpdateProfile();

  const [f, setF] = useState({
    full_name: '', phone: '', district: '', state: '', pincode: '',
    preferred_language: i18n.language,
  });
  const [msg, setMsg] = useState<{ kind: 'ok' | 'err'; text: string } | null>(null);

  // Seed the form once the profile arrives.
  useEffect(() => {
    if (!profile) return;
    setF({
      full_name: profile.full_name ?? '',
      phone: profile.phone ?? '',
      district: profile.district ?? '',
      state: profile.state ?? '',
      pincode: profile.pincode ?? '',
      preferred_language: profile.preferred_language ?? i18n.language,
    });
  }, [profile, i18n.language]);

  const set = (k: keyof typeof f) => (v: string) => {
    setF((p) => ({ ...p, [k]: v }));
    setMsg(null);
  };

  const onSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setMsg(null);
    try {
      await update.mutateAsync({
        full_name: f.full_name.trim(),
        phone: f.phone.trim() || null,
        district: f.district.trim() || null,
        state: f.state.trim() || null,
        pincode: f.pincode.trim() || null,
        preferred_language: f.preferred_language,
      });
      if (f.preferred_language !== i18n.language) {
        void i18n.changeLanguage(f.preferred_language);
        persistLang(f.preferred_language);
      }
      await refresh();
      setMsg({ kind: 'ok', text: t('profile.saved') });
    } catch (err) {
      setMsg({ kind: 'err', text: err instanceof ApiError ? err.message : t('common.error_body') });
    }
  };

  return (
    <div className="space-y-6">
      <PageHeader title={t('nav.profile')} />

      <Card className="max-w-2xl space-y-4">
        <div className="flex flex-wrap items-center gap-2">
          {profile?.role && <Badge tone="info">{t(`auth.role_${profile.role}`)}</Badge>}
          {isFpo && <Badge tone="success">FPO</Badge>}
          {profile?.verification_status && <Badge>{profile.verification_status}</Badge>}
        </div>

        <form onSubmit={onSubmit} noValidate className="space-y-4">
          {msg && (
            <p role="alert" className={
              msg.kind === 'ok'
                ? 'rounded-md bg-success-container px-3 py-2 text-body text-primary-on-container'
                : 'rounded-md bg-danger-container px-3 py-2 text-body text-danger-on-container'
            }>
              {msg.text}
            </p>
          )}

          <Field label={t('auth.full_name')} htmlFor="p-name" required>
            <Input id="p-name" value={f.full_name} required
                   onChange={(e) => set('full_name')(e.target.value)} />
          </Field>

          <div className="grid gap-4 sm:grid-cols-2">
            <Field label={t('auth.phone')} htmlFor="p-phone">
              <Input id="p-phone" inputMode="numeric" value={f.phone}
                     onChange={(e) => set('phone')(e.target.value)} />
            </Field>
            <Field label={t('common.language')} htmlFor="p-lang">
              <Select id="p-lang" value={f.preferred_language}
                      onChange={(e) => set('preferred_language')(e.target.value)}>
                {LANGS.map((l) => <option key={l.code} value={l.code}>{l.label}</option>)}
              </Select>
            </Field>
          </div>

          <div className="grid gap-4 sm:grid-cols-3">
            <Field label={t('auth.district')} htmlFor="p-district">
              <Input id="p-district" value={f.district}
                     onChange={(e) => set('district')(e.target.value)} />
            </Field>
            <Field label={t('auth.state')} htmlFor="p-state">
              <Input id="p-state" value={f.state} onChange={(e) => set('state')(e.target.value)} />
            </Field>
            <Field label={t('auth.pincode')} htmlFor="p-pin">
              <Input id="p-pin" inputMode="numeric" value={f.pincode}
                     onChange={(e) => set('pincode')(e.target.value)} />
            </Field>
          </div>

          <Button type="submit" loading={update.isPending}>{t('common.save')}</Button>
        </form>
      </Card>
    </div>
  );
}
