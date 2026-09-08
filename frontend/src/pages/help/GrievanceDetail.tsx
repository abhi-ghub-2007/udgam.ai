/**
 * One case: what was reported, what happened since, and what you can do next.
 *
 * WHY THE BUTTONS COME FROM THE SERVER
 * ------------------------------------
 * `available_actions` is computed by the backend from the same function that
 * authorises the POST. This screen renders whatever that list says and nothing
 * else -- so the UI cannot drift out of step with the rules, and a user who
 * forges a button gets 403 rather than a state change.
 *
 * WHY THERE IS NO "MARK RESOLVED" FOR THE RESPONDENT
 * --------------------------------------------------
 * Because you cannot clear yourself. The respondent may acknowledge, review,
 * ask for more, and PROPOSE an outcome; only the person who raised the case
 * can say it went away. That asymmetry is enforced in services/grievance.py,
 * echoed here only in which buttons exist.
 *
 * Evidence is never rendered from a stored URL. Opening a file asks the server
 * for a signed link that expires in minutes, so a copied address is worthless
 * by the time anyone else sees it.
 */
import { useState } from 'react';
import { useParams } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import {
  useEvidenceLink, useGrievance, useGrievanceAction, useGrievanceMessage,
  useUploadEvidence,
} from '@/hooks/queries';
import { ApiError } from '@/services/api/client';
import {
  Badge, Button, Card, CardSkeleton, CardTitle, ErrorState, Field, PageHeader,
  Select, Textarea,
} from '@/components/ui';
import { CaseTimeline, GrievanceStatusBadge } from '@/components/grievance/GrievanceBits';
import { dateTime } from '@/utils/format';

/** Actions that settle something and therefore need an outcome chosen. */
const NEEDS_RESOLUTION = new Set(['resolve', 'propose_resolution']);

export default function GrievanceDetail() {
  const { t } = useTranslation();
  const { id } = useParams<{ id: string }>();
  const { data, isLoading, isError, refetch } = useGrievance(id);

  const act = useGrievanceAction(id);
  const send = useGrievanceMessage(id);
  const upload = useUploadEvidence(id);
  const link = useEvidenceLink(id);

  const [reply, setReply] = useState('');
  const [pending, setPending] = useState<string | null>(null);   // action awaiting an outcome
  const [resolution, setResolution] = useState('');
  const [note, setNote] = useState('');
  const [error, setError] = useState<string | null>(null);

  if (isLoading) return <CardSkeleton lines={6} />;
  if (isError || !data) {
    return (
      <ErrorState
        title={t('common.error_title')} body={t('common.error_body')}
        onRetry={() => void refetch()} retryLabel={t('common.retry')}
      />
    );
  }

  const c = data.case;

  const run = async (action: string) => {
    setError(null);
    if (NEEDS_RESOLUTION.has(action) && !resolution) {
      setPending(action);          // ask for the outcome first
      return;
    }
    try {
      await act.mutateAsync({
        action,
        resolution: NEEDS_RESOLUTION.has(action) ? resolution : undefined,
        note: note.trim() || undefined,
      });
      setPending(null); setResolution(''); setNote('');
    } catch (err) {
      setError(err instanceof ApiError ? err.message : t('common.error_body'));
    }
  };

  const onFile = async (file: File | undefined) => {
    if (!file) return;
    setError(null);
    try {
      await upload.mutateAsync(file);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : t('common.error_body'));
    }
  };

  const openEvidence = async (evidenceId: string) => {
    setError(null);
    try {
      const res = await link.mutateAsync(evidenceId);
      window.open(res.url, '_blank', 'noopener,noreferrer');
    } catch (err) {
      setError(err instanceof ApiError ? err.message : t('common.error_body'));
    }
  };

  return (
    <div className="max-w-2xl space-y-6">
      <PageHeader
        title={c.case_number}
        subtitle={t(`grievance.sub_${c.subcategory}`)}
        actions={<GrievanceStatusBadge status={c.status} />}
      />

      {/* ------------------------------------------------ what was reported */}
      <Card className="space-y-3">
        <div className="flex flex-wrap items-center gap-2">
          <Badge>{t(`grievance.cat_${c.category}`)}</Badge>
          {/* Neutral by design: "reported by", never "caused by". */}
          <span className="text-label text-ink-muted">
            {data.my_party === 'respondent'
              ? t('grievance.reported_by', { name: data.counterparty_name ?? '' })
              : t('grievance.you_reported')}
          </span>
        </div>

        <p className="whitespace-pre-wrap text-body text-ink">{c.description}</p>

        {/* The order AS IT STOOD when the case was raised. The order has since
            moved on; the complaint is about that moment, so the snapshot is
            what is shown. */}
        {c.context_snapshot?.order_no && (
          <p className="text-label text-ink-muted">
            {c.context_snapshot.order_no}
            {c.context_snapshot.order_status
              ? ` · ${t('grievance.at_the_time', {
                    status: t(`order.status.${c.context_snapshot.order_status}`, {
                      defaultValue: c.context_snapshot.order_status,
                    }),
                  })}`
              : ''}
          </p>
        )}

        {c.proposed_resolution && c.status !== 'RESOLVED' && (
          <p className="rounded-md bg-warning-container px-3 py-2 text-body text-secondary-on-container">
            {t('grievance.proposed', {
              outcome: t(`grievance.res_${c.proposed_resolution}`),
            })}
          </p>
        )}

        {c.resolution && (
          <p className="rounded-md bg-success-container px-3 py-2 text-body text-primary-on-container">
            {t('grievance.outcome', { outcome: t(`grievance.res_${c.resolution}`) })}
            {c.resolution_note ? ` — ${c.resolution_note}` : ''}
          </p>
        )}
      </Card>

      {error && (
        <p role="alert"
           className="rounded-md bg-danger-container px-3 py-2 text-body text-danger-on-container">
          {error}
        </p>
      )}

      {/* ----------------------------------------------------- what you can do */}
      {data.available_actions.length > 0 && (
        <Card className="space-y-3">
          <CardTitle>{t('grievance.actions_title')}</CardTitle>

          {pending && (
            <div className="space-y-3">
              <Field label={t('grievance.choose_outcome')} htmlFor="grv-res" required>
                <Select id="grv-res" value={resolution}
                        onChange={(e) => setResolution(e.target.value)}>
                  <option value="">{t('grievance.choose_outcome')}</option>
                  {data.resolutions.map((r) => (
                    <option key={r} value={r}>{t(`grievance.res_${r}`)}</option>
                  ))}
                </Select>
              </Field>
              <Field label={t('grievance.note_optional')} htmlFor="grv-note">
                <Textarea id="grv-note" rows={2} value={note}
                          onChange={(e) => setNote(e.target.value)} />
              </Field>
              <div className="flex flex-wrap gap-2">
                <Button loading={act.isPending} disabled={!resolution}
                        onClick={() => void run(pending)}>
                  {t(`grievance.act_${pending}`)}
                </Button>
                <Button variant="outline"
                        onClick={() => { setPending(null); setResolution(''); }}>
                  {t('common.cancel')}
                </Button>
              </div>
            </div>
          )}

          {!pending && (
            <div className="flex flex-wrap gap-2">
              {data.available_actions.map((a) => (
                <Button
                  key={a}
                  variant={a === 'resolve' ? 'primary' : 'outline'}
                  loading={act.isPending}
                  onClick={() => void run(a)}
                >
                  {t(`grievance.act_${a}`)}
                </Button>
              ))}
            </div>
          )}
        </Card>
      )}

      {/* ------------------------------------------------------------ timeline */}
      <Card className="space-y-3">
        <CardTitle>{t('grievance.timeline_title')}</CardTitle>
        <CaseTimeline events={data.timeline} />
      </Card>

      {/* ----------------------------------------------------------- messages */}
      <Card className="space-y-4">
        <CardTitle>{t('grievance.messages_title')}</CardTitle>

        {data.messages.length === 0 && (
          <p className="text-body text-ink-muted">{t('grievance.no_messages')}</p>
        )}

        <ul className="space-y-3">
          {data.messages.map((m) => (
            <li key={m.id} className="rounded-md bg-surface-low px-3 py-2">
              <p className="text-label font-semibold text-ink">
                {m.sender_name || t(`grievance.role_${m.sender_party}`)}
                <span className="ml-2 font-normal text-ink-muted">
                  {dateTime(m.created_at)}
                </span>
              </p>
              <p className="whitespace-pre-wrap text-body text-ink">{m.message}</p>
            </li>
          ))}
        </ul>

        {c.status !== 'CLOSED' && (
          <div className="space-y-2">
            <Field label={t('grievance.reply_label')} htmlFor="grv-reply">
              <Textarea id="grv-reply" rows={3} value={reply} maxLength={2000}
                        onChange={(e) => setReply(e.target.value)} />
            </Field>
            <Button
              loading={send.isPending} disabled={!reply.trim()}
              onClick={async () => {
                setError(null);
                try { await send.mutateAsync(reply.trim()); setReply(''); }
                catch (err) {
                  setError(err instanceof ApiError ? err.message : t('common.error_body'));
                }
              }}
            >
              {t('grievance.send')}
            </Button>
          </div>
        )}
      </Card>

      {/* ----------------------------------------------------------- evidence */}
      <Card className="space-y-3">
        <CardTitle>{t('grievance.evidence_title')}</CardTitle>
        <p className="text-label text-ink-muted">{t('grievance.evidence_private')}</p>

        {data.evidence.length > 0 && (
          <ul className="space-y-2">
            {data.evidence.map((e) => (
              <li key={e.id} className="flex items-center justify-between gap-2">
                <span className="truncate text-body text-ink">
                  {e.file_type} · {Math.round(e.file_size / 1024)} KB
                </span>
                <Button size="sm" variant="outline" loading={link.isPending}
                        onClick={() => void openEvidence(e.id)}>
                  {t('grievance.evidence_open')}
                </Button>
              </li>
            ))}
          </ul>
        )}

        {c.status !== 'CLOSED' && (
          <Field label={t('grievance.evidence_add')} htmlFor="grv-file"
                 hint={t('grievance.evidence_hint')}>
            <input
              id="grv-file" type="file"
              accept="image/jpeg,image/png,image/webp,application/pdf"
              disabled={upload.isPending}
              className="block w-full text-body text-ink file:mr-3 file:rounded-md file:border-0 file:bg-primary-container file:px-3 file:py-2 file:text-label file:font-semibold file:text-primary-on-container"
              onChange={(e) => {
                void onFile(e.target.files?.[0]);
                e.target.value = '';    // allow re-picking the same file
              }}
            />
          </Field>
        )}
      </Card>
    </div>
  );
}
