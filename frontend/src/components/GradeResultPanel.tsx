/**
 * AI-1 grading result — the auditable panel from PRD §13 step 2.
 *
 * The grade is never presented as a bare verdict: every feature score the
 * OpenCV heuristic computed is shown, alongside the method label
 * (HEURISTIC, never REAL or ALGORITHMIC — services/grading.py is a genuine
 * image-processing pipeline, not a trained model) so a farmer can see WHY a
 * grade was given, not just what it was.
 */
import { useTranslation } from 'react-i18next';
import { Button, Card } from '@/components/ui';
import { MethodBadge } from '@/components/ui/Provenance';
import type { GradeResult } from '@/types/api';

export function GradeResultPanel({ grade, onConfirm }: {
  grade: GradeResult; onConfirm: () => void;
}) {
  const { t } = useTranslation();
  const pct = Math.round((grade.confidence || 0) * 100);
  const f = grade.features || {};

  const featureRows: Array<[string, number | undefined]> = [
    [t('market.f_colour'), f.color_score],
    [t('market.f_blemish'), f.blemish_score],
    [t('market.f_shape'), f.shape_score],
    [t('market.f_sharpness'), f.sharpness_score],
  ];

  return (
    <Card className="space-y-4 border-insight/25 bg-insight/5 animate-fade-up">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <span className="text-label font-semibold uppercase tracking-[0.04em] text-insight">
          {t('ai.method')}
        </span>
        <MethodBadge method={grade.method} />
      </div>

      <h2 className="text-h1 font-bold text-ink">
        {t(`market.quality_${grade.grade.toLowerCase()}`)}
      </h2>
      <p className="text-body text-ink-muted">{t('ai.confidence')}: {pct}%</p>

      {f.score != null && (
        <p className="text-body text-ink">
          <strong>{t('market.composite_score')}</strong>: {f.score}/100
        </p>
      )}

      {grade.reasons?.length > 0 && (
        <ul className="space-y-1.5">
          {grade.reasons.map((r, i) => (
            <li key={i} className="flex gap-2 text-body text-ink-muted">
              <span aria-hidden className="mt-2 h-1.5 w-1.5 shrink-0 rounded-full bg-insight" />
              {r}
            </li>
          ))}
        </ul>
      )}

      <dl className="grid grid-cols-2 gap-x-4 gap-y-2 border-t border-line-card pt-4 sm:grid-cols-4">
        {featureRows.map(([label, score]) => (
          <div key={label}>
            <dt className="text-label text-ink-muted">{label}</dt>
            <dd className="tnum text-body font-semibold text-ink">
              {score != null ? `${score}/100` : '—'}
            </dd>
          </div>
        ))}
      </dl>

      <p className="rounded-md bg-surface-low px-3 py-2 text-label text-ink-muted">
        {t('market.quality_not_size')}
      </p>

      <Button block onClick={onConfirm}>{t('market.confirm_grade')}</Button>
    </Card>
  );
}
