/**
 * Notifications.
 *
 * Rows store an i18n KEY plus params rather than a rendered sentence
 * (db/SCHEMA.sql), so a notification written while the user was in English
 * still reads correctly in Hindi or Marathi. An unrecognised key degrades to
 * the notification `type` rather than printing a raw dotted key at the user.
 */
import { useTranslation } from 'react-i18next';
import { useMarkAllRead, useMarkRead, useNotifications } from '@/hooks/queries';
import {
  Button, Card, CardSkeleton, EmptyState, ErrorState, LinkButton, PageHeader, cx,
} from '@/components/ui';
import { date } from '@/utils/format';

export default function Notifications() {
  const { t } = useTranslation();
  const q = useNotifications();
  const markRead = useMarkRead();
  const markAll = useMarkAllRead();

  const items = q.data?.items ?? [];
  const unread = q.data?.unread_count ?? 0;

  /** A stored key renders through t(); anything unrecognised falls back. */
  const line = (key: string, params: Record<string, unknown>, fallback: string): string => {
    if (!key) return fallback;
    const text = String(t(key, params as never));
    return text === key ? fallback : text;
  };

  return (
    <div className="space-y-6">
      <PageHeader
        title={t('market.notifications_title')}
        actions={unread > 0 ? (
          <Button variant="outline" loading={markAll.isPending} onClick={() => markAll.mutate()}>
            {t('market.mark_all_read')}
          </Button>
        ) : undefined}
      />

      {q.isLoading ? (
        <div className="space-y-3">{Array.from({ length: 3 }).map((_, i) => <CardSkeleton key={i} lines={2} />)}</div>
      ) : q.isError ? (
        <ErrorState
          title={t('common.error_title')} body={t('common.error_body')}
          retryLabel={t('common.retry')} onRetry={() => void q.refetch()}
        />
      ) : items.length === 0 ? (
        <EmptyState
          title={t('market.notifications_empty')}
          action={<LinkButton to="/">{t('common.go_home')}</LinkButton>}
        />
      ) : (
        <div className="space-y-3">
          {items.map((n) => {
            const isUnread = !n.read_at;
            return (
              <Card
                key={n.id}
                className={cx('space-y-2 animate-fade-up',
                  isUnread ? 'border-l-[3px] border-l-primary' : 'opacity-75')}
              >
                <div className="flex flex-wrap items-start justify-between gap-2">
                  <strong className="text-body text-ink">
                    {line(n.title_key, n.params, n.type || t('market.notification'))}
                  </strong>
                  <span className="text-label text-ink-muted">{date(n.created_at)}</span>
                </div>
                <p className="text-body text-ink-muted">{line(n.body_key, n.params, '')}</p>
                {isUnread ? (
                  <Button variant="ghost" size="sm"
                          onClick={() => markRead.mutate(n.id)}
                          loading={markRead.isPending && markRead.variables === n.id}>
                    {t('market.mark_read')}
                  </Button>
                ) : (
                  <span className="text-label text-ink-muted">{t('market.read')}</span>
                )}
              </Card>
            );
          })}
        </div>
      )}
    </div>
  );
}
