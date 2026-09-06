/**
 * T-7: transport requests waiting on this transporter.
 *
 * This page used to list orders needing transport and say "Available after
 * acceptance" — the details were withheld until you had already agreed, and
 * agreement was not actually asked for anywhere: the arranger booked you.
 * Now the offer arrives with everything needed to answer it, and answering is
 * the point of the screen.
 *
 * The layout follows the decision a driver is actually making, top to bottom:
 * can I physically do this (weight, window), where does it take me (route),
 * what do I get (pay), then yes or no. Nothing else competes for attention.
 */
import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useAnswerTransportOffer, useTransportJobs } from '@/hooks/queries';
import { ApiError } from '@/services/api/client';
import {
  Badge, Button, Card, CardSkeleton, EmptyState, ErrorState, Input, PageHeader, cx,
} from '@/components/ui';
import { money, number, date } from '@/utils/format';
import type { TransportJob } from '@/types/api';

/** "in 3 h" / "in 2 days" / "expired" — a driver needs the pressure, not a
    timestamp they have to subtract from now. */
function useCountdown() {
  const { t } = useTranslation();
  return (iso: string | null): { label: string; urgent: boolean } | null => {
    if (!iso) return null;
    const ms = new Date(iso).getTime() - Date.now();
    if (ms <= 0) return { label: t('transporter.offer_expired'), urgent: true };
    const hours = Math.round(ms / 3_600_000);
    if (hours < 24) return { label: t('transporter.expires_in_hours', { n: hours }), urgent: hours <= 6 };
    return { label: t('transporter.expires_in_days', { n: Math.round(hours / 24) }), urgent: false };
  };
}

function Leg({ label, address, contact, phone, when, instructions }: {
  label: string; address: string | null; contact: string | null;
  phone: string | null; when: string | null; instructions: string | null;
}) {
  return (
    <div className="space-y-1">
      <p className="text-label text-ink-muted">{label}</p>
      <p className="text-body font-semibold text-ink">{address ?? '—'}</p>
      {when && <p className="tnum text-label text-ink-muted">{when}</p>}
      {(contact || phone) && (
        <p className="text-label text-ink-muted">
          {[contact, phone].filter(Boolean).join(' · ')}
        </p>
      )}
      {instructions && <p className="text-label text-ink-muted">{instructions}</p>}
    </div>
  );
}

function JobCard({ job }: { job: TransportJob }) {
  const { t } = useTranslation();
  const answer = useAnswerTransportOffer();
  const countdown = useCountdown();
  const [declining, setDeclining] = useState(false);
  const [reason, setReason] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [outcome, setOutcome] = useState<'accepted' | 'declined' | null>(null);

  const expiry = countdown(job.expires_at);
  const expired = expiry?.label === t('transporter.offer_expired');

  const send = async (kind: 'accept' | 'decline') => {
    setError(null);
    try {
      await answer.mutateAsync({ offerId: job.offer_id, answer: kind, reason: reason || undefined });
      setOutcome(kind === 'accept' ? 'accepted' : 'declined');
    } catch (err) {
      // 409 is not a fault: somebody else accepted first. Say so plainly
      // rather than showing a generic failure.
      setError(err instanceof ApiError
        ? (err.status === 409 ? t('transporter.job_taken') : err.message)
        : t('common.error_body'));
    }
  };

  if (outcome) {
    return (
      <Card className="space-y-2 animate-fade-up">
        <Badge tone={outcome === 'accepted' ? 'success' : 'neutral'}>
          {t(outcome === 'accepted' ? 'transporter.job_accepted' : 'transporter.job_declined')}
        </Badge>
        <p className="text-body text-ink-muted">
          {t(outcome === 'accepted'
            ? 'transporter.job_accepted_body' : 'transporter.job_declined_body')}
        </p>
      </Card>
    );
  }

  return (
    <Card className="space-y-4 animate-fade-up">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div>
          <h2 className="text-h2 font-semibold text-ink">
            {job.pickup.address && job.drop.address
              ? `${job.pickup.address.split(',')[0]} → ${job.drop.address.split(',')[0]}`
              : (job.order_no ?? t('market.shipment'))}
          </h2>
          <p className="tnum text-label text-ink-muted">
            {number(job.cargo_kg)} {t('common.kg')}
            {job.route_km != null && ` · ${number(job.route_km)} km`}
          </p>
        </div>
        {expiry && (
          <Badge tone={expiry.urgent ? 'danger' : 'neutral'}>{expiry.label}</Badge>
        )}
      </div>

      {/* The one thing that can make the job impossible, said before anything
          else the driver might weigh. */}
      {!job.fits && (
        <p role="alert" className="rounded-md bg-danger-container px-3 py-2 text-body text-danger-on-container">
          {t('transporter.does_not_fit', {
            load: number(job.cargo_kg), free: number(job.available_capacity_kg),
          })}
        </p>
      )}

      <div className="grid gap-4 border-t border-line-card pt-4 sm:grid-cols-2">
        <Leg
          label={t('transporter.pickup')}
          address={job.pickup.address}
          contact={job.pickup.contact_name}
          phone={job.pickup.contact_phone}
          when={job.pickup.from
            ? `${date(job.pickup.from)}${job.pickup.until ? ` – ${date(job.pickup.until)}` : ''}`
            : null}
          instructions={job.pickup.instructions}
        />
        <Leg
          label={t('transporter.drop')}
          address={job.drop.address}
          contact={job.drop.contact_name}
          phone={job.drop.contact_phone}
          when={job.drop.deliver_by ? `${t('transporter.deliver_by')} ${date(job.drop.deliver_by)}` : null}
          instructions={job.drop.instructions}
        />
      </div>

      <div className="flex flex-wrap items-baseline justify-between gap-2 border-t border-line-card pt-4">
        <span className="text-body text-ink-muted">
          {t('transporter.estimated_pay')}
          {job.transport_paid_by && (
            <span className="ml-1 text-label">
              ({t('market.paid_by')} {t(`market.party_${job.transport_paid_by}`)})
            </span>
          )}
        </span>
        <span className="tnum text-h2 font-bold text-primary">
          {job.estimated_cost_paise != null ? money(job.estimated_cost_paise) : '—'}
        </span>
      </div>
      <p className="text-label text-ink-muted">{t('transporter.pay_is_an_estimate')}</p>

      {error && (
        <p role="alert" className="rounded-md bg-danger-container px-3 py-2 text-body text-danger-on-container">
          {error}
        </p>
      )}

      {declining ? (
        <div className="space-y-3 border-t border-line-card pt-4">
          <label htmlFor={`why-${job.offer_id}`} className="text-label text-ink-muted">
            {t('transporter.decline_reason')}
          </label>
          <Input
            id={`why-${job.offer_id}`} value={reason} maxLength={500}
            onChange={(e) => setReason(e.target.value)}
          />
          <div className="flex flex-wrap gap-3">
            <Button variant="danger" loading={answer.isPending} onClick={() => void send('decline')}>
              {t('transporter.confirm_decline')}
            </Button>
            <Button variant="outline" onClick={() => setDeclining(false)}>
              {t('common.cancel')}
            </Button>
          </div>
        </div>
      ) : (
        <div className={cx('flex flex-wrap gap-3 border-t border-line-card pt-4')}>
          <Button
            loading={answer.isPending}
            disabled={!job.fits || expired}
            onClick={() => void send('accept')}
          >
            {t('transporter.accept_job')}
          </Button>
          <Button variant="outline" onClick={() => setDeclining(true)}>
            {t('transporter.decline_job')}
          </Button>
        </div>
      )}
    </Card>
  );
}

export default function Jobs() {
  const { t } = useTranslation();
  const q = useTransportJobs();
  const jobs = q.data ?? [];

  return (
    <div className="space-y-6">
      <PageHeader title={t('transporter.offers_title')} subtitle={t('transporter.offers_subtitle')} />
      {q.isLoading ? (
        <div className="space-y-4">
          {Array.from({ length: 2 }).map((_, i) => <CardSkeleton key={i} lines={4} />)}
        </div>
      ) : q.isError ? (
        <ErrorState
          title={t('common.error_title')} body={t('common.error_body')}
          retryLabel={t('common.retry')} onRetry={() => void q.refetch()}
        />
      ) : jobs.length === 0 ? (
        <EmptyState title={t('transporter.no_offers')} body={t('transporter.no_offers_body')} />
      ) : (
        <div className="space-y-4">
          {jobs.map((j) => <JobCard key={j.offer_id} job={j} />)}
        </div>
      )}
    </div>
  );
}
