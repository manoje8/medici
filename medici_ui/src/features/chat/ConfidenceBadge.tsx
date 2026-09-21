import { clsx } from 'clsx';

import { getConfidenceLevel } from '@/utils/citationParser';

interface ConfidenceBadgeProps {
  percentage: number;
  note?: string;
}

export function ConfidenceBadge({ percentage, note }: ConfidenceBadgeProps) {
  const { level, icon, label } = getConfidenceLevel(percentage);

  return (
    <span
      className={clsx(
        'inline-flex items-center gap-1.5 px-3 py-1 text-xs font-semibold rounded-full tracking-wide',
        level === 'high' && 'bg-success-bg text-success border border-success-border',
        level === 'medium' && 'bg-warning-bg text-warning border border-warning-border',
        level === 'low' && 'bg-error-bg text-error border border-error-border'
      )}
      title={note ?? label}
    >
      {icon} {percentage}% confidence
    </span>
  );
}
