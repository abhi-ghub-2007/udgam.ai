/**
 * UDGAM UI primitives.
 *
 * One implementation of each primitive, used everywhere. Every interactive
 * element meets the 48px tap floor (52px for primary actions) because the
 * target user has calloused hands and a low-end capacitive screen -- that is a
 * product constraint from DESIGN.md, not a stylistic preference.
 */
import type { ButtonHTMLAttributes, InputHTMLAttributes, ReactNode, SelectHTMLAttributes, TextareaHTMLAttributes } from 'react';
import { forwardRef } from 'react';
import { Link } from 'react-router-dom';

export const cx = (...parts: Array<string | false | null | undefined>): string =>
  parts.filter(Boolean).join(' ');

/* ------------------------------------------------------------------ Button */
type ButtonVariant = 'primary' | 'secondary' | 'outline' | 'ghost' | 'danger';
type ButtonSize = 'sm' | 'md';

const BUTTON_BASE =
  'inline-flex items-center justify-center gap-2 rounded-md font-semibold ' +
  'transition-colors duration-fast ease-udgam disabled:opacity-50 ' +
  'disabled:pointer-events-none select-none active:scale-[0.99] ' +
  'motion-reduce:active:scale-100';

const BUTTON_VARIANTS: Record<ButtonVariant, string> = {
  primary: 'bg-primary text-primary-on hover:bg-primary-strong',
  secondary: 'bg-secondary text-secondary-on hover:bg-secondary-strong',
  outline: 'border-card border-outline-variant bg-surface text-ink hover:bg-surface-low',
  ghost: 'text-primary hover:bg-primary-container/40',
  danger: 'bg-danger text-danger-on hover:bg-danger-on-container',
};

const BUTTON_SIZES: Record<ButtonSize, string> = {
  sm: 'min-h-tap px-4 text-body',
  md: 'min-h-tap-primary px-5 text-body',
};

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant;
  size?: ButtonSize;
  block?: boolean;
  loading?: boolean;
}

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(function Button(
  { variant = 'primary', size = 'md', block, loading, className, children, disabled, ...rest },
  ref,
) {
  return (
    <button
      ref={ref}
      disabled={disabled || loading}
      className={cx(BUTTON_BASE, BUTTON_VARIANTS[variant], BUTTON_SIZES[size], block && 'w-full', className)}
      {...rest}
    >
      {loading && <Spinner />}
      {children}
    </button>
  );
});

export function LinkButton({
  to, variant = 'primary', size = 'md', block, className, children,
}: {
  to: string; variant?: ButtonVariant; size?: ButtonSize; block?: boolean;
  className?: string; children: ReactNode;
}) {
  return (
    <Link
      to={to}
      className={cx(BUTTON_BASE, BUTTON_VARIANTS[variant], BUTTON_SIZES[size], block && 'w-full', className)}
    >
      {children}
    </Link>
  );
}

function Spinner() {
  return (
    <span
      aria-hidden
      className="h-4 w-4 animate-spin rounded-full border-2 border-current border-r-transparent motion-reduce:animate-none"
    />
  );
}

/* -------------------------------------------------------------------- Card */
export function Card({ className, children, as: As = 'div' }: {
  className?: string; children: ReactNode; as?: 'div' | 'section' | 'article';
}) {
  return (
    <As className={cx('rounded-lg border-card border-line-card bg-surface p-5', className)}>
      {children}
    </As>
  );
}

export function CardTitle({ children, className }: { children: ReactNode; className?: string }) {
  return <h2 className={cx('text-h2 font-semibold text-ink', className)}>{children}</h2>;
}

/* ------------------------------------------------------------------- Badge */
type BadgeTone = 'neutral' | 'success' | 'warning' | 'danger' | 'info' | 'insight';

const BADGE_TONES: Record<BadgeTone, string> = {
  neutral: 'bg-surface-high text-ink-muted',
  success: 'bg-success-container text-primary-on-container',
  warning: 'bg-warning-container text-secondary-on-container',
  danger: 'bg-danger-container text-danger-on-container',
  info: 'bg-tertiary-container text-primary-on-container',
  // Reserved for AI / model output only.
  insight: 'bg-insight/10 text-insight',
};

export function Badge({ tone = 'neutral', children, className }: {
  tone?: BadgeTone; children: ReactNode; className?: string;
}) {
  return (
    <span className={cx(
      'inline-flex items-center gap-1 rounded-full px-2.5 py-1 text-label font-semibold',
      BADGE_TONES[tone], className,
    )}>
      {children}
    </span>
  );
}

/* ------------------------------------------------------------------ Inputs */
export function Field({ label, htmlFor, error, hint, required, children }: {
  label: string; htmlFor: string; error?: string | null; hint?: string;
  required?: boolean; children: ReactNode;
}) {
  return (
    <div className="flex flex-col gap-1.5">
      <label htmlFor={htmlFor} className="text-label font-semibold text-ink">
        {label}
        {required && <span className="ml-0.5 text-danger" aria-hidden>*</span>}
      </label>
      {children}
      {hint && !error && <p className="text-label text-ink-muted">{hint}</p>}
      {error && (
        <p id={`${htmlFor}-error`} role="alert" className="text-label font-medium text-danger">
          {error}
        </p>
      )}
    </div>
  );
}

const CONTROL =
  'w-full min-h-tap rounded-md border-input bg-surface px-3.5 text-body text-ink ' +
  'transition-colors duration-fast ease-udgam';

export const Input = forwardRef<HTMLInputElement, InputHTMLAttributes<HTMLInputElement> & { invalid?: boolean }>(
  function Input({ className, invalid, ...rest }, ref) {
    return (
      <input
        ref={ref}
        aria-invalid={invalid || undefined}
        className={cx(CONTROL, invalid ? 'border-danger' : 'border-outline-variant focus:border-primary', className)}
        {...rest}
      />
    );
  },
);

export const Select = forwardRef<HTMLSelectElement, SelectHTMLAttributes<HTMLSelectElement> & { invalid?: boolean }>(
  function Select({ className, invalid, children, ...rest }, ref) {
    return (
      <select
        ref={ref}
        aria-invalid={invalid || undefined}
        className={cx(CONTROL, 'pr-9', invalid ? 'border-danger' : 'border-outline-variant focus:border-primary', className)}
        {...rest}
      >
        {children}
      </select>
    );
  },
);

export const Textarea = forwardRef<HTMLTextAreaElement, TextareaHTMLAttributes<HTMLTextAreaElement>>(
  function Textarea({ className, ...rest }, ref) {
    return (
      <textarea
        ref={ref}
        className={cx(CONTROL, 'min-h-[96px] resize-y py-3 border-outline-variant focus:border-primary', className)}
        {...rest}
      />
    );
  },
);

/* --------------------------------------------------------------- Skeletons */
export function Skeleton({ className }: { className?: string }) {
  return <div aria-hidden className={cx('skeleton', className)} />;
}

/** A skeleton shaped like the thing it replaces, so loading communicates what. */
export function CardSkeleton({ lines = 3 }: { lines?: number }) {
  return (
    <Card className="space-y-3">
      <Skeleton className="h-5 w-1/3" />
      {Array.from({ length: lines }).map((_, i) => (
        <Skeleton key={i} className={cx('h-4', i === lines - 1 ? 'w-2/3' : 'w-full')} />
      ))}
    </Card>
  );
}

export function StatSkeleton() {
  return (
    <Card className="space-y-3">
      <Skeleton className="h-4 w-24" />
      <Skeleton className="h-8 w-20" />
    </Card>
  );
}

/* ------------------------------------------------------- States: empty/err */
export function EmptyState({ title, body, action }: {
  title: string; body?: string; action?: ReactNode;
}) {
  return (
    <div className="flex flex-col items-center gap-3 rounded-lg border-card border-dashed border-outline-variant bg-surface-low px-6 py-10 text-center">
      <h3 className="text-h2 font-semibold text-ink">{title}</h3>
      {body && <p className="max-w-prose text-body text-ink-muted">{body}</p>}
      {action}
    </div>
  );
}

export function ErrorState({ title, body, onRetry, retryLabel }: {
  title: string; body?: string; onRetry?: () => void; retryLabel: string;
}) {
  return (
    <div
      role="alert"
      className="flex flex-col items-start gap-3 rounded-lg border-card border-danger/30 bg-danger-container/40 px-5 py-5"
    >
      <h3 className="text-h2 font-semibold text-danger-on-container">{title}</h3>
      {/* Never a raw stack trace: the detail goes to the console, the user gets
          a sentence they can act on. */}
      {body && <p className="text-body text-ink-muted">{body}</p>}
      {onRetry && <Button variant="outline" onClick={onRetry}>{retryLabel}</Button>}
    </div>
  );
}

/* -------------------------------------------------------------- Page shell */
export function PageHeader({ title, subtitle, actions }: {
  title: string; subtitle?: string; actions?: ReactNode;
}) {
  return (
    <header className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
      <div className="min-w-0 space-y-1">
        <h1 className="text-h1 font-bold tracking-[-0.02em] text-ink">{title}</h1>
        {subtitle && <p className="text-body text-ink-muted">{subtitle}</p>}
      </div>
      {actions && <div className="flex shrink-0 flex-wrap gap-2">{actions}</div>}
    </header>
  );
}

/** Stat tile. `value` is pre-formatted by the caller (money/number helpers). */
export function StatCard({ label, value, note, tone = 'neutral' }: {
  label: string; value: string; note?: string; tone?: 'neutral' | 'primary' | 'secondary';
}) {
  const accent =
    tone === 'primary' ? 'text-primary'
    : tone === 'secondary' ? 'text-secondary-strong'
    : 'text-ink';
  return (
    <Card className="flex flex-col justify-between gap-2">
      <p className="text-label font-semibold uppercase tracking-[0.04em] text-ink-muted">{label}</p>
      <p className={cx('tnum text-stat font-bold', accent)}>{value}</p>
      {note && <p className="text-label text-ink-muted">{note}</p>}
    </Card>
  );
}
