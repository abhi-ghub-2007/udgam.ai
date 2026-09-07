/**
 * Identity & credential verification, inside the existing Profile page.
 *
 * WHY IT LIVES HERE
 * -----------------
 * Existing users must be able to finish their credentials without recreating
 * an account, and Profile is the one page every role already visits. No new
 * route, no sidebar entry.
 *
 * THE LINE THIS UI HOLDS
 * ----------------------
 * Submitting a credential is not being verified, and the interface never lets
 * those blur. A pending credential shows the clock, the words "awaiting
 * review", and -- where no authorised integration exists at all -- says so
 * outright rather than implying a check is running. Only a status the server
 * returned as `verified` ever renders a tick.
 *
 * Status is icon + text, never colour alone.
 *
 * Only fields relevant to the caller's role are rendered, and the raw value
 * leaves the browser exactly once: what comes back, and what is shown from
 * then on, is the mask.
 */
import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import {
  useMyVerification, useSubmitCredential, useWithdrawCredential,
} from '@/hooks/queries';
import { ApiError } from '@/services/api/client';
import {
  Badge, Button, Card, CardSkeleton, CardTitle, Field, Input, cx,
} from '@/components/ui';
import type { Credential, CredentialStatus, CredentialType } from '@/types/api';

/** Status glyphs. Paired with words everywhere they appear. */
const STATUS_ICON: Record<CredentialStatus | 'not_added', string> = {
  verified: '✓', pending: '◷', rejected: '✕',
  expired: '⚠', unavailable: '—', not_added: '○',
};

const STATUS_TONE: Record<CredentialStatus | 'not_added',
  'success' | 'info' | 'danger' | 'warning' | 'neutral'> = {
  verified: 'success', pending: 'info', rejected: 'danger',
  expired: 'warning', unavailable: 'neutral', not_added: 'neutral',
};

/** Credentials that carry an expiry date worth collecting. */
const EXPIRING: CredentialType[] = ['transport_permit', 'driving_licence', 'crop_insurance'];

function StatusBadge({ status }: { status: CredentialStatus | 'not_added' }) {
  const { t } = useTranslation();
  return (
    <Badge tone={STATUS_TONE[status]}>
      <span aria-hidden>{STATUS_ICON[status]}</span> {t(`verify.status_${status}`)}
    </Badge>
  );
}

function CredentialRow({ docType, credential, automated }: {
  docType: CredentialType;
  credential?: Credential;
  automated: boolean;
}) {
  const { t } = useTranslation();
  const submit = useSubmitCredential();
  const withdraw = useWithdrawCredential();
  const [open, setOpen] = useState(false);
  const [value, setValue] = useState('');
  const [expiresOn, setExpiresOn] = useState('');
  const [error, setError] = useState<string | null>(null);

  const status: CredentialStatus | 'not_added' = credential?.status ?? 'not_added';
  const inputId = `cred-${docType}`;

  const onSubmit = async () => {
    setError(null);
    try {
      await submit.mutateAsync({
        doc_type: docType,
        value,
        expires_on: EXPIRING.includes(docType) && expiresOn ? expiresOn : undefined,
      });
      setValue('');            // the raw value does not linger in the DOM
      setExpiresOn('');
      setOpen(false);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : t('verify.error'));
    }
  };

  return (
    <li className="space-y-2 border-t border-line-card py-3 first:border-0 first:pt-0">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <p className="text-body font-semibold">{t(`verify.doc_${docType}`)}</p>
          {credential?.masked_value && (
            <p className="tnum text-label text-ink-muted">{credential.masked_value}</p>
          )}
        </div>
        <StatusBadge status={status} />
      </div>

      {/* Say what is actually happening. "Pending" with no explanation reads as
          "a check is running", which would be untrue where no integration
          exists to run one. */}
      {status === 'pending' && (
        <p className="text-label text-ink-muted">
          {automated ? t('verify.pending_automated') : t('verify.pending_manual')}
        </p>
      )}
      {status === 'rejected' && credential?.rejected_reason && (
        <p className="text-label text-danger">{credential.rejected_reason}</p>
      )}
      {status === 'verified' && credential?.provider && (
        <p className="text-label text-ink-muted">
          {t('verify.verified_by', { provider: credential.provider })}
        </p>
      )}
      {credential?.expiry === 'expiring_soon' && (
        <p className="text-label text-secondary-strong">{t('verify.expiring_soon')}</p>
      )}
      {credential?.expiry === 'expired' && (
        <p className="text-label text-secondary-strong">{t('verify.expired_note')}</p>
      )}

      {!open ? (
        <div className="flex flex-wrap gap-2">
          <Button variant="outline" onClick={() => setOpen(true)}>
            {credential ? t('verify.update') : t('verify.add')}
          </Button>
          {credential && (
            <Button
              variant="outline"
              loading={withdraw.isPending}
              onClick={() => void withdraw.mutateAsync(docType).catch(() => {})}
            >
              {t('verify.remove')}
            </Button>
          )}
        </div>
      ) : (
        <div className="space-y-2 rounded-md bg-surface-low p-3">
          <Field label={t(`verify.doc_${docType}`)} htmlFor={inputId}>
            <Input
              id={inputId}
              value={value}
              autoComplete="off"
              onChange={(e) => setValue(e.target.value)}
              placeholder={t(`verify.placeholder_${docType}`, { defaultValue: '' })}
            />
          </Field>
          {EXPIRING.includes(docType) && (
            <Field label={t('verify.valid_until')} htmlFor={`${inputId}-exp`}>
              <Input id={`${inputId}-exp`} type="date" value={expiresOn}
                     onChange={(e) => setExpiresOn(e.target.value)} />
            </Field>
          )}
          {error && (
            <p role="alert" className="text-label text-danger">{error}</p>
          )}
          <div className="flex flex-wrap gap-2">
            <Button loading={submit.isPending} onClick={() => void onSubmit()}>
              {t('verify.submit')}
            </Button>
            <Button variant="outline" onClick={() => { setOpen(false); setValue(''); setError(null); }}>
              {t('common.cancel')}
            </Button>
          </div>
          <p className="text-label text-ink-muted">{t('verify.privacy_note')}</p>
        </div>
      )}
    </li>
  );
}

export function VerificationPanel() {
  const { t } = useTranslation();
  const q = useMyVerification();

  if (q.isLoading) return <CardSkeleton lines={5} />;
  // Verification is additive: if it fails, the rest of Profile still works.
  if (q.isError || !q.data) return null;

  const { credentials, applicable, progress, verification_mode, automated_available } = q.data;
  const byType = new Map(credentials.map((c) => [c.doc_type, c]));

  return (
    <Card className="space-y-5">
      <div>
        <CardTitle>{t('verify.title')}</CardTitle>
        <p className="text-body text-ink-muted">{t('verify.why')}</p>
      </div>

      {/* A demonstration simulator must never be mistakable for the real
          thing, so it is announced before any status is read. */}
      {verification_mode === 'demo' && (
        <p className="rounded-md bg-secondary-container px-3 py-2 text-label text-secondary-on-container">
          {t('verify.demo_mode')}
        </p>
      )}

      {/* Identity: the one requirement every role shares. Stated as a single
          section so PAN and Aadhaar are not asked for twice. */}
      <section className="space-y-2">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <h3 className="text-body font-semibold">{t('verify.identity')}</h3>
          <StatusBadge status={progress.identity_verified
            ? 'verified'
            : progress.identity_submitted ? 'pending' : 'not_added'} />
        </div>
        <p className="text-label text-ink-muted">{t('verify.identity_hint')}</p>
        <ul>
          {applicable.identity.map((docType) => (
            <CredentialRow
              key={docType} docType={docType}
              credential={byType.get(docType)}
              automated={Boolean(automated_available[docType])}
            />
          ))}
        </ul>
      </section>

      {applicable.role_credentials.length > 0 && (
        <section className="space-y-2 border-t border-line-card pt-4">
          <h3 className="text-body font-semibold">{t('verify.role_credentials')}</h3>
          <p className="text-label text-ink-muted">{t('verify.role_hint')}</p>
          <ul>
            {applicable.role_credentials.map((docType) => (
              <CredentialRow
                key={docType} docType={docType}
                credential={byType.get(docType)}
                automated={Boolean(automated_available[docType])}
              />
            ))}
          </ul>
        </section>
      )}

      {/* Progress, as counts. Not a trust score -- there is no defensible
          methodology behind a percentage here, so none is shown. */}
      <div className="space-y-1.5 border-t border-line-card pt-4">
        <p className="text-label font-semibold uppercase tracking-[0.04em] text-ink-muted">
          {t('verify.progress')}
        </p>
        <p className="text-body">
          {progress.identity_verified ? t('verify.identity_done') : t('verify.identity_todo')}
        </p>
        {progress.role_credentials_total > 0 && (
          <p className="text-body text-ink-muted">
            {t('verify.role_progress', {
              verified: progress.role_credentials_verified,
              submitted: progress.role_credentials_submitted,
              total: progress.role_credentials_total,
            })}
          </p>
        )}
      </div>
    </Card>
  );
}

/** Trust indicators for someone ELSE's profile: statuses only, no values.
 *  Rendered wherever a counterparty is shown. */
export function TrustBadges({ identityVerified, credentials = [], compact = false }: {
  identityVerified: boolean;
  credentials?: CredentialType[];
  compact?: boolean;
}) {
  const { t } = useTranslation();
  if (!identityVerified && credentials.length === 0) return null;
  return (
    <div className={cx('flex flex-wrap items-center gap-1.5', compact && 'gap-1')}>
      {identityVerified && (
        <Badge tone="success"><span aria-hidden>✓</span> {t('verify.badge_identity')}</Badge>
      )}
      {credentials.map((c) => (
        <Badge key={c} tone="success">
          <span aria-hidden>✓</span> {t(`verify.doc_${c}`)}
        </Badge>
      ))}
    </div>
  );
}
