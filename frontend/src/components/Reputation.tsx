/**
 * F-8: reputation, and leaving it.
 *
 * Two pieces: a panel that shows what a counterparty has earned (so it can be
 * weighed BEFORE agreeing to deal with them), and a form that appears on a
 * finished order.
 *
 * A star average on its own is easy to read and easy to over-trust, so the
 * counts sit next to it: how many orders completed, how many arrived on time,
 * how many were cancelled. Those come from real rows — a metric the data
 * cannot answer is left out rather than shown as zero. And because one person
 * can be a good farmer and a slow payer, the average is shown for the role
 * being judged, not for the human in general.
 */
import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useLeaveFeedback, useOrderFeedback, useProfileReviews } from '@/hooks/queries';
import { ApiError } from '@/services/api/client';
import {
  Badge, Button, Card, CardSkeleton, CardTitle, EmptyState, Textarea, cx,
} from '@/components/ui';
import { number, date } from '@/utils/format';
import type { PerformanceStats, Role } from '@/types/api';

/** Five buttons, not a slider: a rating is a choice among five things. */
function StarPicker({ value, onChange }: { value: number; onChange: (n: number) => void }) {
  const { t } = useTranslation();
  return (
    <div role="radiogroup" aria-label={t('review.rate')} className="flex gap-1">
      {[1, 2, 3, 4, 5].map((n) => (
        <button
          key={n} type="button" role="radio" aria-checked={value === n}
          aria-label={`${n}`} onClick={() => onChange(n)}
          className={cx(
            'min-h-tap min-w-tap rounded-md px-2 text-h2 transition-colors duration-fast',
            n <= value ? 'text-secondary' : 'text-ink-muted hover:text-ink',
          )}
        >
          <span aria-hidden>{n <= value ? '★' : '☆'}</span>
        </button>
      ))}
    </div>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <dt className="text-label text-ink-muted">{label}</dt>
      <dd className="tnum text-body font-semibold text-ink">{value}</dd>
    </div>
  );
}

function Performance({ stats }: { stats: PerformanceStats }) {
  const { t } = useTranslation();
  const cells: Array<[string, string]> = [];
  if (stats.completed != null) cells.push([t('review.completed'), number(stats.completed)]);
  if (stats.on_time != null && stats.on_time_of)
    cells.push([t('review.on_time'), `${stats.on_time} / ${stats.on_time_of}`]);
  if (stats.cancelled != null) cells.push([t('review.cancelled'), number(stats.cancelled)]);
  if (stats.disputed) cells.push([t('review.disputed'), number(stats.disputed)]);
  if (!cells.length) return null;
  return (
    <dl className="grid grid-cols-2 gap-x-4 gap-y-2 border-t border-line-card pt-4 sm:grid-cols-4">
      {cells.map(([l, v]) => <Stat key={l} label={l} value={v} />)}
    </dl>
  );
}

/** Someone's record, for the role they are being considered for. */
export function ReputationPanel({ profileId, role, compact }: {
  profileId: string | undefined; role?: Role; compact?: boolean;
}) {
  const { t } = useTranslation();
  const q = useProfileReviews(profileId, role);

  if (q.isLoading) return <CardSkeleton lines={3} />;
  if (q.isError || !q.data) return null;
  const d = q.data;

  return (
    <Card className="space-y-4">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <CardTitle>{t('transporter.reliability')}</CardTitle>
        {role && <Badge tone="neutral">{t(`review.as_${role}`)}</Badge>}
      </div>

      {d.review_count === 0 ? (
        <EmptyState title={t('review.none')} body={t('review.none_body')} />
      ) : (
        <>
          <div className="flex items-baseline gap-2">
            <span className="tnum text-display font-bold text-primary">
              {d.avg_rating?.toFixed(1)}
            </span>
            <span aria-hidden className="text-h2 text-secondary">★</span>
            <span className="text-label text-ink-muted">
              {t('review.based_on', { n: d.review_count })}
            </span>
          </div>

          <Performance stats={d.performance} />

          {!compact && d.reviews.length > 0 && (
            <ul className="space-y-3 border-t border-line-card pt-4">
              {d.reviews.map((r) => (
                <li key={r.id} className="space-y-1">
                  <div className="flex flex-wrap items-center gap-2">
                    <span aria-hidden className="text-secondary">
                      {'★'.repeat(r.rating)}<span className="text-ink-muted">{'☆'.repeat(5 - r.rating)}</span>
                    </span>
                    <span className="text-label text-ink-muted">{date(r.created_at)}</span>
                  </div>
                  {r.comment && <p className="text-body text-ink-muted">{r.comment}</p>}
                  {r.tags.length > 0 && (
                    <div className="flex flex-wrap gap-1">
                      {r.tags.map((tag) => (
                        <Badge key={tag} tone="neutral">{t(`review.tag.${tag}`, tag)}</Badge>
                      ))}
                    </div>
                  )}
                </li>
              ))}
            </ul>
          )}

          {/* Says where these came from, so nobody reads them as imported
              third-party reviews. */}
          <p className="text-label text-ink-muted">{t('review.demo_note')}</p>
        </>
      )}
    </Card>
  );
}

/** The review form on a finished order. */
export function ReviewPanel({ orderId }: { orderId: string | undefined }) {
  const { t } = useTranslation();
  const q = useOrderFeedback(orderId);
  const leave = useLeaveFeedback(orderId);
  const [open, setOpen] = useState<string | null>(null);
  const [rating, setRating] = useState(5);
  const [comment, setComment] = useState('');
  const [error, setError] = useState<string | null>(null);

  if (q.isLoading || q.isError || !q.data) return null;
  const d = q.data;
  if (d.counterparties.length === 0) return null;

  const submit = async (rateeId: string) => {
    setError(null);
    try {
      await leave.mutateAsync({ ratee_id: rateeId, rating, comment: comment || undefined });
      setOpen(null);
      setComment('');
      setRating(5);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : t('common.error_body'));
    }
  };

  return (
    <Card className="space-y-4">
      <CardTitle>{t('review.title')}</CardTitle>

      {/* An unfinished order says why, rather than hiding the section. */}
      {!d.can_review && <p className="text-body text-ink-muted">{t('review.not_yet')}</p>}

      {error && (
        <p role="alert" className="rounded-md bg-danger-container px-3 py-2 text-body text-danger-on-container">
          {error}
        </p>
      )}

      <ul className="space-y-3">
        {d.counterparties.map((c) => (
          <li key={c.profile_id} className="space-y-2 border-t border-line-card pt-3 first:border-0 first:pt-0">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <div>
                <p className="text-body font-semibold text-ink">{c.full_name ?? '—'}</p>
                {c.role_on_order && (
                  <p className="text-label text-ink-muted">{t(`review.as_${c.role_on_order}`)}</p>
                )}
              </div>
              {c.already_reviewed ? (
                <Badge tone="success">{t('review.submitted')}</Badge>
              ) : d.can_review ? (
                <Button variant="outline" onClick={() => setOpen(open === c.profile_id ? null : c.profile_id)}>
                  {t('review.leave')}
                </Button>
              ) : null}
            </div>

            {c.already_reviewed && c.my_review && (
              <p className="text-label text-ink-muted">
                <span aria-hidden className="text-secondary">{'★'.repeat(c.my_review.rating)}</span>
                {c.my_review.comment && ` ${c.my_review.comment}`}
              </p>
            )}

            {open === c.profile_id && !c.already_reviewed && (
              <div className="space-y-3">
                <StarPicker value={rating} onChange={setRating} />
                <Textarea
                  aria-label={t('review.comment')} maxLength={1000} value={comment}
                  placeholder={t('review.comment')}
                  onChange={(e) => setComment(e.target.value)}
                />
                <Button loading={leave.isPending} onClick={() => void submit(c.profile_id)}>
                  {t('review.submit')}
                </Button>
              </div>
            )}
          </li>
        ))}
      </ul>
    </Card>
  );
}
