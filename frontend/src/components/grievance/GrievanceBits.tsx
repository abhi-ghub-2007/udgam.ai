/**
 * The small pieces the grievance screens share.
 *
 * NEUTRAL LANGUAGE IS A DESIGN CONSTRAINT HERE
 * --------------------------------------------
 * A grievance is an allegation until it is settled. Nothing in this file
 * renders a word that assigns blame: the badge says "Under review", never
 * "Disputed by buyer"; the timeline says "Resolution proposed", never
 * "Admitted". If it turns out to be nobody's fault, the record should not have
 * spent a week implying otherwise.
 *
 * Every label is an i18n key. `status_${lowercased}` maps the database's
 * ACTION_REQUIRED onto "Action needed" in en/hi/mr, which is also why the raw
 * enum never reaches a screen.
 */
import { useTranslation } from 'react-i18next';
import { useNavigate } from 'react-router-dom';
import { Badge, Button } from '@/components/ui';
import { dateTime } from '@/utils/format';
import type { GrievanceEvent, GrievanceStatus } from '@/types/api';

/** Tone carries meaning that colour alone must not: every badge also has text.
    Amber for "somebody is waiting on you", green only once it is actually
    settled -- an escalated case is not a success. */
const TONE: Record<GrievanceStatus, 'neutral' | 'info' | 'warning' | 'success' | 'danger'> = {
  OPEN: 'info',
  ACKNOWLEDGED: 'info',
  UNDER_REVIEW: 'info',
  ACTION_REQUIRED: 'warning',
  RESOLVED: 'success',
  REOPENED: 'warning',
  ESCALATED: 'danger',
  CLOSED: 'neutral',
};

export function GrievanceStatusBadge({ status }: { status: GrievanceStatus }) {
  const { t } = useTranslation();
  return (
    <Badge tone={TONE[status] ?? 'neutral'}>
      {t(`grievance.status_${status.toLowerCase()}`)}
    </Badge>
  );
}

/**
 * The auditable timeline.
 *
 * Rendered from `grievance_events`, which no participant can write to -- there
 * is deliberately no INSERT policy on that table. So this is the system's
 * account of what happened, not either side's, which is the only reason it is
 * worth showing.
 */
export function CaseTimeline({ events }: { events: GrievanceEvent[] }) {
  const { t } = useTranslation();
  if (events.length === 0) return null;

  return (
    <ol className="space-y-0">
      {events.map((e, i) => (
        <li key={e.id} className="relative flex gap-3 pb-4 last:pb-0">
          {/* The connecting rail. Stops at the last item so the timeline does
              not appear to continue into events that have not happened. */}
          {i < events.length - 1 && (
            <span aria-hidden
                  className="absolute left-[5px] top-4 h-full w-px bg-line-card" />
          )}
          <span aria-hidden
                className="relative mt-1.5 h-2.5 w-2.5 shrink-0 rounded-full bg-primary" />
          <div className="min-w-0 flex-1">
            <p className="text-body text-ink">
              {t(`grievance.event_${e.event_type}`, {
                defaultValue: t('grievance.event_updated'),
              })}
            </p>
            <p className="text-label text-ink-muted">{dateTime(e.created_at)}</p>
          </div>
        </li>
      ))}
    </ol>
  );
}

/**
 * "Report an issue", placed on the screen where the problem actually happened.
 *
 * It carries the order id in the URL so the case opens with the order, the
 * counterparty and the order's status already attached. Nobody retypes an
 * order number into a complaint form -- and, more importantly, nobody gets to
 * NAME their own respondent: the backend derives that from the order it reads
 * back under the caller's own RLS scope.
 */
export function ReportIssueButton({ orderId, className }:
  { orderId?: string; className?: string }) {
  const { t } = useTranslation();
  const navigate = useNavigate();
  return (
    <Button
      variant="outline"
      className={className}
      onClick={() => navigate(orderId ? `/help/new?order=${orderId}` : '/help/new')}
    >
      {t('grievance.report_issue')}
    </Button>
  );
}
