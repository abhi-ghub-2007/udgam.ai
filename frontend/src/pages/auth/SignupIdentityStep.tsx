/**
 * The optional identity step, shown once the account already exists.
 *
 * WHY IT CANNOT BLOCK SIGNUP
 * --------------------------
 * By the time this renders, supabase.auth.signUp, the session and
 * POST /api/auth/register have all succeeded -- the account is complete and
 * usable. So every failure path here ends the same way: the user continues to
 * their dashboard. Skipping is a first-class button, not a hidden escape.
 *
 * It asks for ONE credential, not a compliance form. PAN or Aadhaar, either
 * satisfies the identity requirement, and the copy says plainly that this is
 * about other users trusting you rather than about paperwork.
 *
 * Submitting does NOT verify. The server returns `pending`, and this step says
 * so rather than showing a tick the moment the field is filled.
 */
import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useSubmitCredential } from '@/hooks/queries';
import { ApiError } from '@/services/api/client';
import { Button, Card, Field, Input, Select } from '@/components/ui';

type IdentityType = 'pan' | 'aadhaar_last4';

export function SignupIdentityStep({ onDone }: { onDone: () => void }) {
  const { t } = useTranslation();
  const submit = useSubmitCredential();
  const [docType, setDocType] = useState<IdentityType>('pan');
  const [value, setValue] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [submitted, setSubmitted] = useState(false);

  const onSubmit = async () => {
    setError(null);
    try {
      await submit.mutateAsync({ doc_type: docType, value });
      setValue('');                    // do not leave the raw value in the DOM
      setSubmitted(true);
    } catch (err) {
      // A failure here must not strand a brand-new account, so the continue
      // button stays available underneath.
      setError(err instanceof ApiError ? err.message : t('verify.error'));
    }
  };

  if (submitted) {
    return (
      <Card className="space-y-4">
        <div className="space-y-1">
          <h2 className="text-h2 font-semibold">{t('signup_identity.received_title')}</h2>
          <p className="text-body text-ink-muted">{t('signup_identity.received_body')}</p>
        </div>
        <Button onClick={onDone}>{t('signup_identity.continue')}</Button>
      </Card>
    );
  }

  return (
    <Card className="space-y-4">
      <div className="space-y-1">
        <h2 className="text-h2 font-semibold">{t('signup_identity.title')}</h2>
        <p className="text-body text-ink-muted">{t('signup_identity.why')}</p>
      </div>

      <Field label={t('signup_identity.choose')} htmlFor="su-doc-type">
        <Select id="su-doc-type" value={docType}
                onChange={(e) => { setDocType(e.target.value as IdentityType); setValue(''); }}>
          <option value="pan">{t('verify.doc_pan')}</option>
          <option value="aadhaar_last4">{t('verify.doc_aadhaar_last4')}</option>
        </Select>
      </Field>

      <Field label={t(`verify.doc_${docType}`)} htmlFor="su-doc-value">
        <Input
          id="su-doc-value" value={value} autoComplete="off"
          inputMode={docType === 'aadhaar_last4' ? 'numeric' : 'text'}
          placeholder={t(`verify.placeholder_${docType}`, { defaultValue: '' })}
          onChange={(e) => setValue(e.target.value)}
        />
      </Field>

      {error && (
        <p role="alert" className="rounded-md bg-danger-container px-3 py-2 text-body text-danger-on-container">
          {error}
        </p>
      )}

      <p className="text-label text-ink-muted">{t('verify.privacy_note')}</p>

      <div className="flex flex-wrap gap-2">
        <Button loading={submit.isPending} disabled={!value.trim()}
                onClick={() => void onSubmit()}>
          {t('verify.submit')}
        </Button>
        {/* Skipping is offered plainly. The account already works. */}
        <Button variant="outline" onClick={onDone}>
          {t('signup_identity.skip')}
        </Button>
      </div>
      <p className="text-label text-ink-muted">{t('signup_identity.later')}</p>
    </Card>
  );
}
