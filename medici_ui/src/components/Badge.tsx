import { clsx } from 'clsx';
import type { ReactNode } from 'react';

interface BadgeProps {
  variant?: 'primary' | 'success' | 'warning' | 'error' | 'info';
  children: ReactNode;
  className?: string;
}

const variantClasses: Record<NonNullable<BadgeProps['variant']>, string> = {
  primary:
    'bg-primary-glow text-primary-light border border-primary-light',
  success:
    'bg-success-bg text-success border border-success-border',
  warning:
    'bg-warning-bg text-warning border border-warning-border',
  error:
    'bg-error-bg text-error border border-error-border',
  info:
    'bg-primary-glow text-accent-light border border-primary-light',
};

export function Badge({ variant = 'primary', children, className }: BadgeProps) {
  return (
    <span
      className={clsx(
        'inline-flex items-center gap-1.5 px-3 py-1 text-xs font-semibold rounded-full tracking-wide',
        variantClasses[variant],
        className
      )}
    >
      {children}
    </span>
  );
}
